# FlexWeek

Constraint scheduler for a student week. Places homework around school and sports, then explains why something moved.

Congressional App Challenge 2026. Python solver, HTML/CSS/JS interface, individual accounts and saved weeks. No chatbot or product demo mode.

## Run

Requires Python 3.14.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Open **http://127.0.0.1:8000** and create an account. Usernames use 3–32 letters,
numbers or underscores; passwords use 12–128 characters. Accounts start with an
empty week. Add school/sports as locked blocks, add homework as flexible tasks,
and press Solve. Every editor save goes to your account; Solve previews placement
without replacing your entered blocks.

Choose Nocturne (dark) or Slate (light) from Theme. The choice is saved to your
account. If a save fails, keep the page open and use Retry save. A conflicting
save from another window offers a draft download and reload of the saved week.
Password recovery is planned for the later hardening phase.

Existing browser-only weeks can be explicitly imported after sign-in. Import
replaces the account's current week after confirmation; invalid legacy data is
left untouched. Private account weeks are not stored in localStorage.

## Storage and hosting configuration

| Variable | Default | Purpose |
|---|---|---|
| `FLEXWEEK_DATABASE` | `var/flexweek.db` | SQLite account, session, week and theme storage |
| `FLEXWEEK_ORIGIN` | `http://127.0.0.1:8000` | Exact browser origin, including port |

For a different local port, set `FLEXWEEK_ORIGIN` to match. Non-local origins
require HTTPS. HTTPS deployments use Secure session cookies. A hosted release
needs a persistent database directory and backups; an ephemeral filesystem
loses accounts and schedules. Configure trusted reverse proxies explicitly so
client-address throttling sees the intended source. Full deployment, account
recovery, deletion/retention policy and security audits remain later work.

The database and its journals are gitignored. Back up the database with SQLite's
backup API or with the app stopped; protect backups as private account data.

## Checks

```bash
.venv/bin/python -m compileall -q backend
.venv/bin/ruff check .
.venv/bin/mypy backend
.venv/bin/pytest -q
node --check frontend/app.js
node --test frontend/tests/accounts.test.mjs
```

Node is used only for development tests, not to build or run the web app. The
frontend tests exercise account/save state with a simulated document; they do
not replace checking the real browser layout.

## Progress

Phases 3 and 4 are complete: accounts, saved weeks and Daily Scheduler themes
are verified in the real desktop web engine. See the [roadmap](roadmap.md) for
the separate desktop app, calendar interaction port, later design work and
contest delivery. Windows/Linux are
desktop targets; the Windows executable still needs to be built and tested.

A Linux desktop build exists: a PySide6 `QWebEngineView` window with the FastAPI
backend bundled inside it. It needs no separate server and no Python install —
run `dist/FlexWeek/FlexWeek` and it starts its own backend on a loopback port,
keeping its database next to the browser profile in your user data directory.
Build it with `pip install -r requirements-desktop.txt` then
`./desktop/build_linux.sh`. Releases ship as a tarball attached to a GitHub
Release rather than committed to the repository, because the bundled Qt
WebEngine library exceeds GitHub's per-file limit; see [DESKTOP.md](DESKTOP.md). Set `FLEXWEEK_DESKTOP_ORIGIN` to point the window at
a hosted deployment instead; local and hosted accounts are separate, without
automatic synchronization. Linux rebuilds preserve the previous artifact.

Windows build preparation is in `desktop/build_windows.ps1`, with setup and
remaining platform checks in [DESKTOP.md](DESKTOP.md). No Windows executable has
been verified yet. Daily Scheduler's Nocturne/Slate colors are adapted from the
GPL-3.0 `Local-Schedule-Assistant` project. AI assistance was used in development,
including Codex and GLM-5.3 Flash test contribution; the runtime uses no AI service.

Submit by Sunday, October 25, 2026, 8:00 p.m. PDT.

License: GPL-3.0. Contributor listing is pending completion before submission.
