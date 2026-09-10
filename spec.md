# FlexWeek

## Problem
Students plan by guilt, not by constraints: a to-do list has no idea that school
runs 08:00–14:30, practice takes the evening, and a three-hour paper is due
tomorrow. FlexWeek takes a student's fixed week (school, sport, commute, sleep)
plus their assignments, places the assignments in the gaps with a constraint
solver, and explains in plain English every time something could not be placed
or had to move. Built as a Congressional App Challenge 2026 entry. Working title
was *Reslot*; the public name is **FlexWeek**. The original Sep 6 contest brief
is archived in `docs/cac-build-plan.md`. Living schedule and remaining work live
in `roadmap.md`.

## Intended Users
High-school students using individual accounts through the web app and the
separate desktop app. New accounts start with an empty week; no anonymous demo
mode or sample-data fallback. Secondary audience: CAC judges, who create an
account and can inspect the GitHub repository.

Scope revision approved 2026-09-06: accounts, shared persistence, Daily Scheduler
Nocturne/Slate themes first. Desktop delivery, calendar interaction, cascade,
slack, focus timers and alarms later shipped under that approval. Visual
redesign and audits remain deferred. The previous Oct 3 feature freeze is
superseded by the expanded roadmap.

## Required Behavior
Contract for the finished app:

- A week is a set of `TimeBlock`s: `locked` blocks have a fixed `start`;
  `flexible` blocks have a `duration_min` and a deadline (`latest`) and are
  placed by the solver.
- Optional block fields the API and storage already keep: `category`,
  `completed`, `completed_day`, `missed_days`, `spotify_url`, `focus_sessions`,
  `focus_minutes`, and pomodoro split fields (`pomodoro_parent_id`,
  `pomodoro_role`, `pomodoro_index`). `completed_day` is only valid on a
  completed flexible block that has a `start` on one of its candidate days.
  `missed_days` is only valid on a locked block, and every missed day must be one
  of that block's `days`.
- A week has unique block ids. A pomodoro parent cannot be stored in the same
  week as the chunks split from it.
- The solver places every flexible block on the 15-minute grid (Mon–Sun,
  06:00–23:00) without overlapping any locked block or any other placed block.
- Search order respects priority (1 = test, 2 = quiz, 3 = homework,
  4 = reading); a higher-priority block wins a contested slot.
- Energy windows (`high` / `medium` / `low`) are a soft preference on value
  order, never a hard constraint.
- Every unplaced block and every move carries a machine reason code, rendered as
  a plain-English sentence: `LOCKED_OVERLAP`, `DEADLINE_MISS`, `NO_SLOT_LEFT`,
  `PRIORITY_PREEMPT`, `ENERGY_MISMATCH` (soft), `SLEEP_GUARD`,
  `RESHUFFLE_AFTER_MISS`.
- Sleep (23:00–06:00) is a guard the solver never places into and never steals.
- Solving is capped at 150 ms. On timeout the app returns the best partial
  placement plus reasons for what is unplaced. It never hangs and never
  returns nothing.
- Cascade: marking a locked occurrence as missed re-solves remaining flexible
  blocks and lists the resulting diffs as moves. Sleep stays intact. Details
  live in `docs/scheduling-recovery.md`.
- Deadline slack is shown as ok / tight / danger.
- Edge cases: an unsolvable week returns `complete: false` with reasons rather
  than an error; a duration that is not a positive multiple of 15 is rejected in
  both the browser form and the API. Legacy browser data is explicitly imported
  into a signed-in account; invalid data stays untouched and never loads a demo.

## User Experience
Web app, one page, desktop-first (designed at 1280px) and usable on a phone at
390px. Vanilla JavaScript, HTML5 and CSS. **No npm, no build step, no
framework**. FastAPI serves `frontend/` as static files, so there is one origin
and no CORS.

First paint with no session is Create account. Log in is a separate screen.
A new account is offered a short first-week setup (school hours, one sport,
then homework). Every step can be skipped. Dragging or clicking empty grid
space opens an Add dialog for that range.

Downloads from GitHub Releases:

- **Download for Windows.** `FlexWeek-Windows-x64.zip`
- **Download for Linux.** `FlexWeek-Linux-x86_64.tar.gz`

Windows: extract the zip first; running from inside the zip does not work.
Until the app is code-signed, SmartScreen is More info, then Run anyway.
Linux: 64-bit desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or
newer, OpenGL or EGL. The X11 cursor helper is inside the archive. A shippable
Linux tarball is built on Ubuntu 24.04, not on a newer-glibc Fedora host.
Chromebooks use the web app when a hosted URL exists.

Run locally:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload    # then open http://127.0.0.1:8000/
```

Current account/API contract:

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/auth/register` | Create username/password account and session |
| POST | `/api/auth/login` | Authenticate and rotate session |
| POST | `/api/auth/logout` | Revoke current session |
| GET | `/api/auth/me` | Current account; 401 when absent/expired |
| GET/PUT | `/api/week` | One dated week of the account, with revision-checked saves |
| GET | `/api/weeks` | The `week_start` dates this account has saved, ascending |
| GET/PUT | `/api/preferences` | Theme, reminders, timers, alarms, Spotify default |
| POST | `/api/solve` | Authenticated week in, SolveTrace out; no storage mutation |
| GET | `/api/health` | Public health response |

`POST /api/solve` accepts `{ "blocks": [...] }` and an optional `recover`
object for a missed locked occurrence. The solve trace contains `placed`,
`unplaced`, `moves`, `explanations`, `failed_constraints`, `solve_ms`,
`complete`. Demo endpoints are removed. Test-only seed JSON remains.
Writes require `X-FlexWeek-Request: 1`; browser origins must match
`FLEXWEEK_ORIGIN`. Clients send `X-FlexWeek-Account` to reject requests after a
cross-tab account change. No CORS is enabled.

Registration: normalized case-insensitive ASCII username (3–32 letters, digits,
underscores), password 12–128 characters. New accounts have an empty week and
Nocturne theme. Duplicate usernames return 409, invalid input 422, expired or
missing sessions 401, stale changed writes 409, throttled auth 429, oversized
requests 413, transient database failures 503. Identical week retries return
success without duplicate blocks or another revision increment.

A week is identified by `(account, week_start)`, where `week_start` is a naive
local ISO date that is always a Monday. An account holds as many dated weeks as
it saves, each with its own revision. A never-saved week reads as empty at
revision 0 rather than 404, and a `week_start` that is malformed, out of
2000-01-01..2099-12-31, or not a Monday is rejected with 422 rather than snapped
to the nearest Monday, so a client and the server cannot disagree about which
week is open while both believe they succeeded. Blocks keep their `days` index
and derive their calendar date, so the solver stays day-index pure.
A week has at most 100 uniquely identified blocks; titles 1–80,
course names at most 40, durations positive multiples of 15 up to 7140 minutes,
and unique day indices. Explicit starts are on the visible grid and end by
23:00. Deadlines/earliest bounds use full English weekday plus HH:MM, or HH:MM.
API write bodies are capped at 256 KiB.

Preferences store `theme` (`nocturne` or `slate`), reminder enable/lead/sound,
`reminder_dnd_override`, pomodoro lengths, `auto_split_pomodoro`,
`default_spotify_url`, and a list of alarms. On desktop, `reminder_dnd_override`
tags the Notification `flexweek-stay` so the tray presenter skips the 10-second
auto-close. Unchecked alerts still close at 10 seconds. Qt has no
`requireInteraction`.

## Architecture
- Language/runtime: **Python 3.14**. PINNED. Verified against the local
  interpreter (3.14.7) and `.github/workflows/verify.yml` (`python-version: '3.14'`).
  Never downgrade.
- Current languages: Python, JavaScript, HTML5, CSS, and SQL for account storage.
  The desktop shell is PySide6 (Qt WebEngine); see DESKTOP.md.
- Frameworks, pinned in `requirements.txt`: FastAPI 0.141.1,
  uvicorn[standard] 0.52.4, pytest 9.1.1, httpx 0.28.1, ruff 0.16.6, mypy 2.3.1, Pydantic 2.13.5.
- Storage: SQLite at `FLEXWEEK_DATABASE` (default `var/flexweek.db`), with users,
  sessions, weeks keyed `(user_id, week_start)`, preferences and short-lived
  auth-attempt counters. Schema creation is additive on startup; related writes
  use transactions. The pre-dated single-week table migrates on first start
  inside one explicit transaction, stamping the existing row with the Monday of
  that day; it is idempotent and never drops a row. Browser
  localStorage is read only for explicit legacy import, then removed on success.
- Major components:
  - `backend/models.py`. Pydantic models (`TimeBlock`, `Move`, `SolveTrace`,
    `Explanation`) and slot helpers. **Zero FastAPI imports.**
  - `backend/app.py`. HTTP endpoints, authentication/ownership, static files, `/api/solve`.
    No placement logic.
  - `backend/solver.py`. Pure synchronous CSP placement. No HTTP knowledge.
  - `backend/explain.py`. Reason code and slack status to English string.
  - `backend/storage.py`. SQLite transactions, password hashing and sessions.
  - `backend/data/demo_*.json`. Test-only anonymized seed weeks.
  - `backend/tests/`. Pytest suite; the source of truth for solver behavior.
  - `frontend/`. `index.html`, `styles.css`, and deferred scripts sharing one
    global scope: `app.js` (week state, grid, saves, solve, alarms), `auth.js`
    (Create account / Log in), `editor.js` (Add/Edit dialog), `setup.js`
    (first-week setup), `focus.js` (timer and Now / Next). The browser owns
    interaction and explanation display and **never reimplements placement**.
  - `desktop/`. PySide6 window, bundled uvicorn, packaging scripts, and
    isolated WebEngine probes.
- Time model: local `HH:MM` strings and Mon–Sun day indices, assumed
  America/Los_Angeles. No timezone conversion math anywhere in v1.
- Slot grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week.
  Overlap uses half-open ranges `[start, end)`. One `overlaps()` helper. There
  is no duplicate date math.
- External APIs/services: none. No OAuth, no calendar sync, no LLM at runtime.
- Deployment: hosted web backend plus a separate desktop client. The Linux
  desktop build ships as a PySide6 Qt WebEngine window that runs the FastAPI
  backend in-process on a loopback port, so it needs no separate server and no
  Python install; its database sits beside the browser profile in the user data
  directory. `FLEXWEEK_DESKTOP_ORIGIN` (or `FLEXWEEK_ORIGIN`) points that window
  at a hosted deployment instead, and an invalid value is an error rather than a
  silent fall back to local. Windows zip is built on GitHub Actions
  (`.github/workflows/release-windows.yml`); extracting and running it on a
  real PC is unverified here. Production requires HTTPS via FLEXWEEK_ORIGIN and
  persistent SQLite storage.
- GitHub Actions: `.github/workflows/verify.yml` is the source gate (mypy, not
  pyright). `.github/workflows/codeql.yml` runs CodeQL on Python and JavaScript.
  The generic kit `ci.yml` is not installed: it ran pyright and looked for
  `tests/` at the repo root. Dependabot stays off.

## Security & Privacy
- No secrets in source. All credentials via environment variables. The app
  uses account session credentials generated at runtime.
- Dependencies must be pinned and reproducible. Updates are manual:
  **Dependabot is deliberately not used in this repo**. Do not add
  `.github/dependabot.yml` or re-enable it.
- Account-owned schedules are sent to the backend and stored in SQLite.
- Passwords use Python/OpenSSL scrypt, N=32768, r=8, p=3, random 16-byte salt,
  32-byte derived key; comparison is constant-time. No new hash dependency.
- Opaque random sessions expire in seven days; only SHA-256 token hashes are
  stored. Cookies are HttpOnly, SameSite=Strict, Secure on HTTPS deployments.
  Sign-out revokes the current session. Expired sessions are rejected on reads
  and cleaned when new sessions are created.
- Writes use custom-header/origin CSRF checks; endpoints derive ownership from
  the session. Queries are parameterized. No credentials or schedule payloads
  are logged; validation responses omit submitted input.
- Auth attempts are bounded per username (10) and source address (30) per
  five-minute window, persisted in SQLite and expired during auth requests.
- Production needs HTTPS, database backups, and deployment-specific proxy setup.
  Recovery, deletion/retention policy, advanced hardening and audits are deferred
  to Phase 6 before public release.
- Failed saves retain in-memory drafts with retry, download and reload controls.
  Stale revisions never silently overwrite newer data. Session loss hides all
  private content; a draft can restore only after the same account signs in.
  Explicit sign-out discards drafts after confirmation.
- Demo data is anonymized: no real student names, schools, or addresses, and no
  copyrighted syllabus PDFs in the repo.
- License is **GPL-3.0** (`LICENSE`); the README and the page footer must agree
  with it. Chosen deliberately: copyleft means anyone who redistributes a
  modified FlexWeek has to publish their source, so the scheduler cannot be
  quietly repackaged into a closed product that students cannot inspect.
- AI assistance is disclosed in the README and the CAC form; the solver is
  handwritten.

## Validation & Tooling
The full source gate from the repo root, inside `.venv`, is:

```
.venv/bin/python scripts/verify.py
```

`--web-only` omits desktop tests and reports desktop as unverified.
`.github/workflows/verify.yml` runs that variant on every push and pull
request (Python 3.14, Node 24, `contents: read`). It installs nothing and does
not build a binary.

The commands it runs, each of which must exit 0:

- Lint: `ruff check .`. Configured in `ruff.toml` (target `py314`, line length
  110). The `DTZ` (timezone-aware datetime) rules are deliberately not selected
  because of the naive-local-time model above; the reason is written into
  `ruff.toml`. Do not add timezone math to satisfy a linter.
- Types: `mypy backend`. This repo's type checker is mypy. Do not install
  pyright.
- Tests: `pytest -q`. Run from the repo root so `backend` imports resolve.
  `--web-only` limits pytest to `backend/tests`.
- Frontend behavior tests: `node --test frontend/tests/*.test.mjs` (the shell
  glob; the directory form is broken on Node 24);
  syntax: `node --check` on every `frontend/*.js` file. Node is development-only,
  with no npm packages or frontend build step. Browser layout needs a separate
  manual check.
- Preserve existing solver fixture coverage; include account isolation, expiry,
  CSRF, atomic saves, revision conflict and import/retry tests.
- Solver tests are the source of truth: `solve()` stays synchronous and pure so
  pytest can exercise it without HTTP.

## Acceptance Criteria
- [ ] Only-locked week solves to an identity schedule with 0 moves (T1).
- [ ] A single homework block with room to spare is placed, energy-matched where
      possible (T2).
- [ ] Test vs. reading contending for one slot: test placed, reading unplaced
      with `PRIORITY_PREEMPT` (T3).
- [ ] 6h of homework into 2h of free time: remainder unplaced with
      `NO_SLOT_LEFT` (T4).
- [ ] Deadline before the only free window: unplaced with `DEADLINE_MISS` (T5).
- [ ] A flexible block's domain excludes slots covered by a sport block (T6).
- [ ] The packed fixture reports `solve_ms < 150` (T7).
- [ ] Corrupt legacy localStorage does not replace the account week or load demos.
- [ ] Two accounts independently create, solve, save and reload weeks.
- [ ] Sign-out hides private data; expired sessions cannot read/write/solve.
- [ ] Nocturne/Slate theme persists per account.
- [ ] Failed saves preserve drafts; stale saves return a recoverable conflict.
- [ ] No output block overlaps another, and no flexible block starts after its
      deadline (property tests).
- [ ] First paint with no session is Create account, not Log in.
- [ ] A pomodoro parent cannot be stored with the chunks split from it.
- [ ] Marking a locked occurrence missed reshuffles remaining flexible work and
      leaves sleep intact.
- [ ] Download names are `FlexWeek-Windows-x64.zip` and
      `FlexWeek-Linux-x86_64.tar.gz`.
- [ ] A public Render URL loads the app and a judge can follow the README.
- [ ] `scripts/verify.py` exits 0 (`ruff check .`, `mypy backend`, and
      `pytest -q` included).
- [ ] CHANGELOG.md updated for user-visible changes.
