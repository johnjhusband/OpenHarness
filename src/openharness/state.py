"""SQLite + FTS5 message bus. Every inbox/outbox/escalation/tick logged here.

Markdown files remain the source of truth. chat.db is the indexed view.
"""
from __future__ import annotations
import sqlite3
import time
import json
from pathlib import Path
from contextlib import contextmanager

from openharness import config


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    sender      TEXT    NOT NULL,
    recipient   TEXT,
    kind        TEXT    NOT NULL,
    correlation TEXT,
    content     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);
CREATE INDEX IF NOT EXISTS idx_messages_kind ON messages(kind);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


def db_path() -> Path:
    cfg = config.load()
    root = Path(cfg["_root"])
    rel = cfg.get("state", {}).get("chat_db", "state/chat.db")
    path = (root / rel).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection():
    path = db_path()
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(SCHEMA)
        yield conn
    finally:
        conn.close()


def append(sender: str, content: str, *, recipient: str | None = None,
           kind: str = "chat", correlation: str | None = None) -> int:
    """Append one message. Returns inserted row id."""
    with connection() as conn:
        ts = time.time()
        cur = conn.execute(
            "INSERT INTO messages (ts, sender, recipient, kind, correlation, content) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, sender, recipient, kind, correlation, content),
        )
        return int(cur.lastrowid or 0)


def tail(since_id: int = 0, limit: int = 50) -> list[dict]:
    """Return up to `limit` messages with id > since_id, NEWEST returned (oldest-first ordering).

    CRITICAL: this is the function CTO got wrong. Returns the LATEST `limit`
    rows when the table has more matching rows than `limit`, not the earliest.
    """
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, ts, sender, recipient, kind, correlation, content "
            "FROM messages WHERE id > ? ORDER BY id DESC LIMIT ?",
            (since_id, limit),
        ).fetchall()
    rows = list(reversed(rows))
    return [
        {"id": r[0], "ts": r[1], "sender": r[2], "recipient": r[3],
         "kind": r[4], "correlation": r[5], "content": r[6]}
        for r in rows
    ]


def search(query: str, limit: int = 20) -> list[dict]:
    """FTS5 search across message content."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT m.id, m.ts, m.sender, m.recipient, m.kind, m.content "
            "FROM messages_fts JOIN messages m ON m.id = messages_fts.rowid "
            "WHERE messages_fts MATCH ? ORDER BY m.id DESC LIMIT ?",
            (query, limit),
        ).fetchall()
    return [
        {"id": r[0], "ts": r[1], "sender": r[2], "recipient": r[3],
         "kind": r[4], "content": r[5]}
        for r in rows
    ]


def cursor_path() -> Path:
    cfg = config.load()
    root = Path(cfg["_root"])
    return (root / cfg.get("state", {}).get("cursor_file", "state/last-tick-cursor.json")).resolve()


def read_cursor() -> dict:
    path = cursor_path()
    if not path.exists():
        return {}
    with path.open() as f:
        return json.load(f)


def write_cursor(cursor: dict) -> None:
    path = cursor_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(cursor, f, indent=2)
