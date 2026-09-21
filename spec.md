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
High-school students using individual accounts through the FlexWeek desktop app
for Windows and Linux. New accounts start with an empty week; no anonymous demo
mode or sample-data fallback. Secondary audience: CAC judges, who create an
account and can inspect the GitHub repository.

Scope revision approved 2026-09-06: accounts, shared persistence, and light and
dark themes first. Desktop delivery, calendar interaction, cascade,
slack, focus timers and alarms later shipped under that approval. Visual
redesign and audits remain deferred. The previous Oct 3 feature freeze is
superseded by the expanded roadmap.

## Required Behavior
Contract for the finished app:

- A week is a set of `TimeBlock`s: `locked` blocks have a fixed `start`;
  `flexible` blocks are work sessions with a `duration_min` that the solver
  places.
- Homework is an account-owned assignment that outlives any one week: `title`,
  an exact `due` (naive local `YYYY-MM-DDTHH:MM`, any minute), `estimate_min`,
  progress (`focus_minutes`, `focus_sessions`) and completion (`completed`,
  `completed_at`), with its own revision. A work session points at its
  assignment with `assignment_id` and takes its title, deadline, priority,
  energy, course, category and Spotify link from it. One assignment can have
  sessions in several weeks. Details live in `docs/stage1-contract.md`.
- The solver stays day-index pure. Before solving, the backend turns an
  assignment's `due` into the week's bound: a due time inside the week bounds
  that day, a due date after the week adds no bound, and a due date before the
  week leaves the session unplaced with `DEADLINE_MISS`.
- Focus minutes never complete anything. Finishing an assignment, or adding time
  to it, is the student's explicit choice when a session ends.
- Old weekday deadlines (`latest`, `"Thursday 21:00"` or `"21:00"`) migrate once
  into assignments on start and are still accepted on saves. A save that uses
  them never changes an existing assignment.
- Optional block fields the API and storage keep: `assignment_id`, `category`,
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
  both the app's editor and the API. Files exported by earlier builds, including
  the retired browser client, import into a signed-in account; invalid data
  stays untouched and never loads a demo.
- Copy, paste, duplicate and copy-day use an in-memory clipboard that clears on
  sign-out, session expiry and account deletion. Fixed-time conflicts are previewed and must be resolved;
  pasted homework keeps the same assignment identity, stays flexible and never
  exceeds its remaining unplanned minutes.
- Account-owned weekly routines contain fixed commitments only. Applying one
  to a Monday-keyed destination week previews every occurrence and lets the
  student omit or adjust one-week exceptions without changing the routine.
- A later week reviews unfinished homework using the original assignment ID,
  exact deadline and progress. Repeated planning and request retries cannot
  duplicate or over-plan it.
- Account-owned restore points snapshot weeks and assignments. Clear week,
  routine application and restore preserve the replaced schedule first; a
  stale restore preview returns 409 and no failure stores partial state. The UI
  labels backups as local-device or hosted-server data.
- New accounts receive eight one-time recovery codes, shown once. A forgotten
  password is recovered with a username, an unused code and a new password, not
  email. Signed-in students can replace leftover codes, change the password or
  delete the account; those writes need the current password. Delete removes
  every row for that user. The username may be registered again.
- `GET /api/storage-info` reports local or hosted `mode`, a student-facing
  `label`, the signed-in `username`, the public `origin` and
  `transfer_limit_bytes` (262144). It never returns a filesystem path.
- Local-to-hosted transfer is a password-gated format-3 export and a previewed
  import of weeks, assignments, preferences and routines. Import takes a Stage 3
  restore point of the destination weeks and assignments first. Automatic
  bidirectional or offline sync is out of scope. Export returns 413 when the
  compact import apply envelope would exceed the 256 KiB write cap.
- Day view lists one date: homework due soon, that day's work sessions and fixed
  commitments, one next action, and a workload summary that separates scheduled
  time, recorded focus time and time still free before 23:00, with a breakdown by
  category. Due soon is open homework due that day or the next, plus anything
  already overdue. Below 800px Day is the default view and Week stays one control
  away. Quick Add homework asks only for title, due date and estimated time, with
  "Choose a time myself" for anything more. The planning button reads "Plan my
  homework", and "Update my plan" once that week has been planned. Details live
  in `docs/stage2-contract.md`.
- Running late is a solve preview of a 15, 30 or 60 minute delay from a
  15-minute cutoff on one day of the open week. Fixed commitments and sleep stay
  put, and work that no longer fits stays unplaced rather than being dropped.
  Accepting it stores one locked "Running late" block through `/api/changes` and
  re-solves, so reload and one-step Undo act on a real saved change. Details
  live in `docs/stage4-contract.md`.
- Spreading a project previews flexible sessions of a chosen length across the
  dates from a start date through the due date. It writes nothing until the
  student confirms, and each session is an ordinary session of the same
  assignment, not a pomodoro split.
- An assignment carries optional `notes` (at most 4000 characters), up to 20
  `links` (`http` or `https` only) and a checklist of up to 40 items. Ticking
  checklist items never completes the assignment, and focus minutes still
  complete nothing.
- Preferences carry availability: up to 21 `protected` windows (downtime,
  commute or meal), up to 21 soft `study_windows`, and an optional `day_cutoff`
  that flexible work must finish by. `POST /api/solve` loads them for the
  signed-in account, so the client never re-sends occupancy.
- Comfort preferences persist per account: `alert_volume` (0-100), `end_chime`,
  `tray_notifications`, `start_at_login`, `preferred_view` (`week` or `day`),
  `sidebar_collapsed` and `sidebar_width_px` (200-640). Defaults stay omitted
  from stored JSON so older clients keep working, and timer rounding to the
  15-minute grid is previewed and explained rather than silent. Details live in
  `docs/stage5-contract.md`.
- Appearance preferences persist per account beside `theme`: `theme_pack`
  (`system`, `light-frost`, `dark-frost`, `nocturne`, `slate`), `accent`
  (`default`, `sky`, `gold`, `sea`, `sand`), `accent_chips`, and `motion`
  (`off`, `normal`, `extra`). Omitted pack leaves `theme` as today's
  light/dark/system choice. A set pack must be stored with `theme` on the
  matching axis (`slate` for `light-frost` and `slate`, `nocturne` for
  `dark-frost` and `nocturne`). Omitted `motion` means the account has never
  stored a level; an explicit `"normal"` stays on the wire so a second device
  cannot treat it as unset. Details live in
  `docs/stage8-appearance-contract.md`.
- Month view shows one calendar month of deadlines, projects, overdue homework
  and study time, planned and completed, and any date opens Day view. A session
  pins to a date only when that date is certain: the day it was completed, or
  its only candidate day. Open work with several candidate days is reported as
  an unscheduled total instead of being painted across all of them, because the
  solver's choice is never stored. Details live in `docs/stage7-contract.md`.

## User Experience
Native desktop app, one window, designed at 1280px and usable down to 1150px,
where the layouts switch to a narrow arrangement. PySide6 Qt widgets over a
FastAPI backend started in-process on a loopback port. **No HTML, CSS or
JavaScript, no npm, no build step, no framework.** There is no browser client:
the web app was retired in September 2026 and `frontend/` deleted.

First paint with no session is Sign in, with creating an account offered as a
line of small print that switches the same card over.
A new account must acknowledge its eight recovery codes, then is offered a
short first-week setup (school hours, one sport, then homework). Every setup
step can be skipped. Dragging or clicking empty grid space opens an Add dialog
for that range.

Downloads from GitHub Releases:

- **Download for Windows.** `FlexWeek-Windows-x64-Setup.exe`
- **Download for Linux.** `FlexWeek-Linux-x86_64.tar.gz`

Windows: `FlexWeek-Windows-x64-Setup.exe` installs for the student's account
without an administrator; `FlexWeek-Windows-x64.msi` installs for every account
on a PC, for schools and IT. Until the app is code-signed, SmartScreen is More
info, then Run anyway.
Linux: 64-bit desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or
newer, OpenGL or EGL. The X11 cursor helper is inside the archive. A shippable
Linux tarball is built on Ubuntu 24.04, not on a newer-glibc Fedora host.
Chromebooks are not supported: there is no web version.

Run locally:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-desktop.txt
python -m desktop.main    # starts the backend inside the app; nothing to open in a browser
```

Current account/API contract:

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/auth/register` | Create username/password account, session and eight one-time recovery codes |
| POST | `/api/auth/login` | Authenticate and rotate session |
| POST | `/api/auth/logout` | Revoke current session |
| GET | `/api/auth/me` | Current account; 401 when absent/expired |
| POST | `/api/auth/recover` | Username, unused recovery code and new password; throttled like login |
| GET | `/api/auth/recovery-status` | Unused recovery-code count |
| POST | `/api/auth/recovery-codes` | Password-gated replacement of unused codes |
| POST | `/api/auth/password` | Change password; keep this session and drop the others |
| DELETE | `/api/auth/account` | Password-gated deletion of this account and its rows |
| GET/PUT | `/api/week` | One dated week of the account, with revision-checked saves |
| GET | `/api/weeks` | The `week_start` dates this account has saved, ascending |
| GET | `/api/day` | One date's agenda: due-soon homework, that day's sessions and fixed blocks, a next action and the workload split |
| GET | `/api/month` | Month grid of deadlines, projects, overdue work, planned and completed study time, and an unscheduled total |
| GET | `/api/assignments` | Open assignments with planned and unplanned minutes for a `week_start`; completed ones only when asked |
| PUT/DELETE | `/api/assignments/{id}` | Revision-checked create, update and delete; delete removes its sessions from every week |
| POST | `/api/assignments/{id}/spread` | Preview sessions of a chosen length from a start date through the due date; writes nothing |
| POST | `/api/changes` | Several week and assignment writes, all or nothing; optional operation ID and pre-change recovery point |
| GET/PUT | `/api/preferences` | Theme, appearance pack, accent, motion, reminders, timers, alarms, Spotify default, availability windows and comfort settings |
| GET | `/api/timer-presets` | Named timer presets on the 15-minute grid |
| GET | `/api/reminder-limits` | The reminder ceilings the settings dialog explains |
| POST | `/api/timer-split-preview` | Explain how a timer splits and rounds before it is saved |
| GET/PUT/DELETE | `/api/routines[/{id}]` | Account-owned, revision-checked fixed-time routine templates |
| GET/POST | `/api/restore-points[/{id}/preview or /restore]` | Create/list restore points, preview a state-tokened diff, and restore transactionally |
| GET | `/api/storage-info` | Authenticated mode, label, username, origin and 256 KiB transfer limit; no filesystem path |
| POST | `/api/account-export` | Password-gated format-3 snapshot of weeks, assignments, preferences and routines |
| POST | `/api/account-import/preview` | State-tokened diff of a format-3 snapshot against this account |
| POST | `/api/account-import` | Previewed replace of weeks, assignments, preferences and routines |
| POST | `/api/solve` | Authenticated week and its `week_start` in, SolveTrace out; no storage mutation |
| GET | `/api/health` | Public health response |

`POST /api/solve` accepts `{ "blocks": [...], "week_start": "YYYY-MM-DD" }` and
either an optional `recover` object for a missed locked occurrence or an
optional `running_late` object for a delayed start, never both. `week_start` is
required when any block carries `assignment_id`. The solve trace contains `placed`,
`unplaced`, `moves`, `explanations`, `failed_constraints`, `solve_ms`,
`complete`. Demo endpoints are removed. Test-only seed JSON remains.
Writes require `X-FlexWeek-Request: 1`; the request `Origin` must match the
API's origin. Clients send `X-FlexWeek-Account` so a request made before an
account change is rejected after it. No CORS is enabled.

Registration: normalized case-insensitive ASCII username (3–32 letters, digits,
underscores), password 12–128 characters. New accounts have an empty week, eight
one-time recovery codes (hashes only in SQLite) and a theme that follows the
device's light or dark setting. Duplicate usernames return 409, invalid input
422, expired or missing sessions 401, stale changed writes 409, throttled auth
429, oversized requests 413, transient database failures 503. Identical week
retries return success without duplicate blocks or another revision increment.
Wrong username and wrong recovery code share one 401 sentence. Account export
and import apply use the same 256 KiB write cap; export 413s when the compact
`{snapshot, state_token, operation_id}` envelope would not fit. Details live in
`docs/stage6-contract.md`.

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
23:00. An assignment's `due` is a naive local `YYYY-MM-DDTHH:MM` between
2000-01-01 and 2099-12-31; `earliest` bounds and legacy `latest` values use a
full English weekday plus HH:MM, or HH:MM. An account holds at most 1000
assignments. API write bodies are capped at 256 KiB.

Preferences store `theme` as `system`, `slate` or `nocturne` for the light/dark
axis. The menus offer appearance packs: System, Light frost, Dark frost,
Nocturne and Slate. Light frost and Dark frost are new looks. `system` is the
default pack: the app follows the device's light or dark setting, uses Light
when the device reports none, and switches when that setting changes. Choosing
Slate, Nocturne or a frost pack keeps that look until the student chooses
again. Signed-out screens follow the device setting; signing out does not
change an account's saved choice. Preferences
also store reminder enable/lead/sound, `reminder_dnd_override`, pomodoro
lengths, `auto_split_pomodoro`, `default_spotify_url`, and a list of alarms. On desktop, `reminder_dnd_override`
tags the Notification `flexweek-stay` so the tray presenter skips the 10-second
auto-close. Unchecked alerts still close at 10 seconds. Qt has no
`requireInteraction`.

## Architecture
- Language/runtime: **Python 3.14**. PINNED. Verified against the local
  interpreter (3.14.7) and `.github/workflows/verify.yml` (`python-version: '3.14'`).
  Never downgrade.
- Current languages: Python, and SQL for account storage. The client is PySide6
  Qt widgets; see DESKTOP.md.
- Frameworks, pinned in `requirements.txt`: FastAPI 0.141.1,
  uvicorn[standard] 0.52.4, pytest 9.1.1, httpx 0.28.1, ruff 0.16.6, mypy 2.3.1, Pydantic 2.13.5.
- Storage: SQLite, in the user data folder for the app (`FLEXWEEK_DATABASE`,
  default `var/flexweek.db`, only when the API runs on its own), with users,
  sessions, weeks keyed `(user_id, week_start)`, assignments keyed
  `(user_id, id)`, preferences, routines, restore points, hashed recovery codes,
  bounded idempotency records and short-lived auth-attempt counters. Schema
  creation is additive on startup; related writes use transactions. The
  pre-dated single-week table migrates on first start inside one explicit
  transaction, stamping the existing row with the Monday of that day; it is
  idempotent and never drops a row. A preferences table from
  before the System theme is rebuilt once on start in one transaction: stored
  `slate` and `nocturne` are kept and any other value becomes `system`. Flexible
  blocks without `assignment_id`, and pomodoro chunk groups, migrate once on
  start into assignments with deterministic ids, inside one transaction and
  without changing week revisions (`docs/stage1-contract.md`). Browser
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
  - `desktop/native/`. The client: `window.py` (chrome, pages and dialogs),
    `controller.py` (session, saves, solve, focus and alarms), `widgets.py`
    (week grid, day agenda, month and editors), `layouts/` (the eight designs
    and the registry they are built from), `look.py` (packs, presets and
    palettes), `weekmodel.py`, `pomodoro.py`, `tones.py` and `sound.py`. The
    client owns interaction and explanation display and **never reimplements
    placement**.
  - `desktop/`. PySide6 window, bundled uvicorn, packaging scripts and assets.
- Time model: local `HH:MM` strings and Mon–Sun day indices, plus naive local
  `YYYY-MM-DDTHH:MM` assignment deadlines, assumed America/Los_Angeles. No
  timezone conversion math anywhere in v1.
- Slot grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week.
  Overlap uses half-open ranges `[start, end)`. One `overlaps()` helper. There
  is no duplicate date math.
- External APIs/services: none. No OAuth, no calendar sync, no LLM at runtime.
- Deployment: the desktop client is the product; there is no web client. The
  Windows and Linux builds are PySide6 Qt widgets that run the FastAPI backend
  in-process on a loopback port, so they need no separate server and no Python
  install; the database sits in the user data directory. `FLEXWEEK_DESKTOP_ORIGIN` (or `FLEXWEEK_ORIGIN`) points that window
  at a hosted deployment instead, and an invalid value is an error rather than a
  silent fall back to local. The Windows installers are built on GitHub
  Actions (`.github/workflows/release-windows.yml`), which installs, opens and
  uninstalls each one; running them on a real PC is unverified here. Production requires HTTPS via FLEXWEEK_ORIGIN and
  persistent SQLite storage.
- GitHub Actions: `.github/workflows/verify.yml` is the source gate (mypy, not
  pyright). `.github/workflows/codeql.yml` runs CodeQL on Python.
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
- Production needs HTTPS, deployment backups and deployment-specific proxy
  setup. Stage 3 restore points cover student recovery inside one account.
  Stage 6 recovery codes, password change, account deletion and previewed
  format-3 transfer are the supported access flows (`docs/stage6-contract.md`).
  Advanced hardening and audits remain later release work.
- The week saves itself shortly after each change. A failed save keeps its
  payload and operation id and is retried automatically, so a retry writes the
  same change once; Retry save appears while one is pending. A save that comes
  back 409 because another window changed the week is never written over:
  saving stops and the student is asked to reload the saved week, which
  discards the unsaved change. Stale revisions never silently overwrite newer
  data. Session loss hides all private content. Opening another week parks an
  unsaved week as a draft for that account. A running focus timer is kept in
  memory per account with ids and times only, never assignment text; undo
  history lives in memory and clears on sign-out, session expiry or account
  deletion.
- The Stage 3 clipboard also lives only in memory and clears on sign-out,
  session expiry and account deletion. Routine, restore and transfer routes derive
  ownership from the session; another account's opaque ID is treated as not
  found. Restore and import previews use a state token so a later edit cannot
  be overwritten silently. Password-gated export, code replacement, password
  change and deletion are not enough from a stolen session cookie alone.
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

`--backend-only` omits desktop tests and reports desktop as unverified.
`.github/workflows/verify.yml` runs that variant on every push and pull
request (Python 3.14, `contents: read`). It installs nothing and does
not build a binary.

The commands it runs, each of which must exit 0:

- Lint: `ruff check .`. Configured in `ruff.toml` (target `py314`, line length
  110). The `DTZ` (timezone-aware datetime) rules are deliberately not selected
  because of the naive-local-time model above; the reason is written into
  `ruff.toml`. Do not add timezone math to satisfy a linter.
- Types: `mypy backend`. This repo's type checker is mypy. Do not install
  pyright.
- Tests: `pytest -q`. Run from the repo root so `backend` imports resolve.
  `--backend-only` limits pytest to `backend/tests`.
- Desktop behavior tests are part of the pytest suite and run offscreen against
  a real loopback backend. Window layout on a real display needs a separate
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
- [ ] A malformed, oversized or newer-version import file is refused without
      touching the account week.
- [ ] Two accounts independently create, solve, save and reload weeks.
- [ ] Sign-out hides private data; expired sessions cannot read/write/solve.
- [ ] A new account follows the device's light or dark setting, and a chosen
      Light or Dark theme is saved per account and returns after logging in.
- [ ] Failed saves preserve drafts; stale saves return a recoverable conflict.
- [ ] No output block overlaps another, and no flexible block starts after its
      deadline (property tests).
- [ ] First paint with no session is Sign in, with creating an account offered
      under it.
- [ ] A pomodoro parent cannot be stored with the chunks split from it.
- [ ] Marking a locked occurrence missed reshuffles remaining flexible work and
      leaves sleep intact.
- [ ] A student enters homework due next Tuesday at 11:59 p.m., works on it
      this week and next, ends a focus session without completing it, switches
      weeks without losing the timer, and undoes an accidental delete or replan.
- [ ] A student copies one practice occurrence, applies a fixed-time routine to
      next week with one holiday exception, carries unfinished homework once,
      and previews and restores an account-owned recovery point.
- [ ] A student recovers a forgotten password with a one-time code, sees which
      account and origin they are using, and previews a format-3 account file
      onto another signed-in account without exposing it to a third account.
- [ ] A new student can see what is due tomorrow, add homework, plan it, start
      it and mark it finished at 390px and 1280px, without a context menu or
      reading scheduling documentation.
- [ ] A student who is running late previews a 30-minute delay, accepts it, and
      undoes it in one step; spreading a project adds sessions only after a
      preview.
- [ ] Protected downtime, preferred study hours and a day cutoff change where
      the solver places work without the client re-sending occupancy.
- [ ] A student opens Month, sees deadlines with planned and completed study
      time, and clicks a date to open Day view.
- [ ] Download names are `FlexWeek-Windows-x64-Setup.exe` (with
      `FlexWeek-Windows-x64.msi` for schools) and
      `FlexWeek-Linux-x86_64.tar.gz`.
- [ ] A judge can install the Windows or Linux download and follow the README.
- [ ] `scripts/verify.py` exits 0 (`ruff check .`, `mypy backend`, and
      `pytest -q` included).
- [ ] CHANGELOG.md updated for user-visible changes.
