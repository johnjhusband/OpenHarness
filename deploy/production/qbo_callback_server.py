#!/usr/bin/env python3
"""Production QBO OAuth callback server — runs on the VPS behind Caddy.

Caddy terminates TLS for https://qbo.husband.llc and reverse-proxies
/qbo-callback and /qbo-start to this server on 127.0.0.1:8910.

Flow:
  1. John (from his laptop browser) opens https://qbo.husband.llc/qbo-start
     → this server builds the Intuit authorize URL (with a random state it
       remembers) and 302-redirects him to Intuit.
  2. John signs in, picks the real company, clicks Authorize.
  3. Intuit redirects to https://qbo.husband.llc/qbo-callback?code=...&realmId=...&state=...
  4. This server validates state, exchanges the code for tokens using the
     PRODUCTION client_id/secret, and writes them to the VPS creds file.
  5. Bookie's daemon picks them up on the next tick.

Reads client_id/client_secret from /root/.config/bookie/qbo-credentials.json
(populated with the PRODUCTION keys once Intuit issues them). environment must
be "production". Writes refresh_token + realm_id back to the same file.
"""
from __future__ import annotations
import base64
import json
import secrets
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CREDS = Path("/root/.config/bookie/qbo-credentials.json")
REDIRECT_URI = "https://qbo.husband.llc/qbo-callback"
SCOPE = "com.intuit.quickbooks.accounting"
AUTHORIZE = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
LISTEN = ("127.0.0.1", 8910)

_state = {"value": None}


def _load_creds() -> dict:
    return json.loads(CREDS.read_text())


def _save_creds(d: dict) -> None:
    CREDS.write_text(json.dumps(d, indent=2))
    CREDS.chmod(0o600)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _html(self, code: int, body: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/qbo-start":
            cfg = _load_creds()
            if not cfg.get("client_id"):
                return self._html(500, "<h1>Not configured: production client_id missing.</h1>")
            _state["value"] = secrets.token_urlsafe(32)
            url = (f"{AUTHORIZE}?client_id={urllib.parse.quote(cfg['client_id'])}"
                   f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
                   f"&scope={urllib.parse.quote(SCOPE)}&response_type=code"
                   f"&state={_state['value']}")
            self.send_response(302)
            self.send_header("Location", url)
            self.end_headers()
            return
        if path == "/qbo-callback":
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if params.get("state") != _state["value"]:
                return self._html(400, "<h1>State mismatch — please restart at /qbo-start.</h1>")
            if not params.get("code") or not params.get("realmId"):
                return self._html(400, "<h1>Missing code or realmId.</h1>")
            cfg = _load_creds()
            auth = base64.b64encode(f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
            body = urllib.parse.urlencode({
                "grant_type": "authorization_code", "code": params["code"],
                "redirect_uri": REDIRECT_URI}).encode()
            req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"})
            try:
                tok = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
            except Exception as e:
                return self._html(500, f"<h1>Token exchange failed: {e}</h1>")
            now = time.time()
            cfg["refresh_token"] = tok["refresh_token"]
            cfg["access_token"] = tok["access_token"]
            cfg["access_token_expires_at"] = now + int(tok.get("expires_in", 3600)) - 60
            if "x_refresh_token_expires_in" in tok:
                cfg["refresh_token_expires_at"] = now + int(tok["x_refresh_token_expires_in"])
            cfg["realm_id"] = params["realmId"]
            cfg["environment"] = "production"
            _save_creds(cfg)
            return self._html(200, "<h1>Bookie is connected to your QuickBooks. "
                                   "You can close this tab.</h1>")
        return self._html(404, "<h1>Not found</h1>")


if __name__ == "__main__":
    HTTPServer(LISTEN, Handler).serve_forever()
