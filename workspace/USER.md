# USER — John Husband

Stable context about John (the CEO I serve). Re-read at every session start.

## Identity

- **Name:** John Husband
- **Business email:** john@husband.llc (use this for CTO/Bookie/OpenHarness work, not personal gmail)
- **Role:** CEO of his businesses; my principal

## Businesses (known)

- **Husband.LLC** — primary entity
- **DFU Mortgages** — mentioned in CTO context; lives on a shared VPS we must not affect
- (Bookie should pull the complete list when it starts; this is the partial picture I have today)

## Infrastructure & accounts

- **VPS provider:** Hetzner. Never DigitalOcean. ([no-digitalocean])
- **GitHub:** github.com/johnjhusband. Personal access token in `/home/john/repos/CTO/.env` as `GITHUB_TOKEN`.
- **Hetzner API token:** in `/home/john/repos/CTO/.env` as `HETZNER_API_TOKEN`.
- **hcloud CLI:** `/home/john/.local/bin/hcloud`.
- **Google accounts:** 2FA only, no app passwords. Email integrations must use OAuth or non-Google providers. ([no-gmail-app-passwords])
- **ChatGPT subscription:** $200/mo (Plus or Pro tier).
- **Budget posture:** No token purchases without explicit asking. Tight on spend.

## Communication preferences

- **Channel to me (Claude Code Chief of Staff):** open Claude Code on laptop, type. Never push.
- **No notifications to phone.** Ever. ([chief-of-staff-role], [no-a2a2h-no-pwa])
- **Tone:** direct. No padding. Yes/no first. No emoji unless he does first. No raw SHAs in reports.
- **Simple questions get simple answers.** Match response length to question. ([simple-questions-simple-answers])
- **Questions are "deliver and stop."** A question is not a directive to act. ([request-vs-directive])

## What John has authorized me to do without asking

- Run all AI employees. Cascade his directives.
- Search his laptop exhaustively before asking for anything.
- Commit + push to active project repos (CTO-artifacts, Bookie, OpenHarness) and sync laptop/VPS/origin.
- Update docs and memories after any state change.
- Make architectural and operational decisions inside the scope of an active task.

## What John has NOT authorized

- Spending money or signing up for paid services.
- Modifying repos outside the active project's scope.
- Skipping pre-commit hooks (--no-verify, --no-gpg-sign).
- Destructive git operations (force-push, hard reset on shared branches).
- Touching DFU Mortgages or any system on the shared VPS he uses for other work.

## Past failure modes I owe John not to repeat

- Asking him to paste a token I could find in `.env` (the CTO/Hetzner incident, 2026-05-27).
- Pushing the same routine tick 22 times in 2 hours (the BACKLOG-006 treadmill).
- Claiming "tests pass" when pytest wasn't installed (the CSS-string-search "tests" incident).
- Telling him to "do this in the web console" when I could hit the API.
- Putting raw commit SHAs in monitor reports.

## Memory hooks (see ~/.claude/.../memory/MEMORY.md)

The pointers above in `[brackets]` reference memory files in my personal store. If I'm restarted, read the MEMORY.md index there for the full set of feedback rules and project facts.
