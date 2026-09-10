# context.md — FlexWeek

## Current State
- Date: 2026-09-09. Branch `feat/phase7-focus-tools`, based on `bfb8edf`.
- Phase 7 focus tools are in: pomodoro timers on placed tasks, standalone
  alarms with a dismiss/snooze dialog, Spotify share links on blocks and
  alarms, a Now / Next line, timer and do-not-disturb preferences, and desktop
  tray notifications. Started by ChatGPT, finished and verified here.
- Gates green: Ruff, mypy over 31 files, 159 Python tests and 67 frontend
  tests, JavaScript syntax.
- Phase 7 is verified in a real browser, not only in the DOM stub. The
  `phase7` WebEngine case starts a focus session and checks the panel counts,
  that pause stops the countdown, that skip changes phase and reset closes it,
  then adds an alarm through the preferences dialog.
- Phase 5 calendar interactions and Phase 6 scheduling recovery remain in
  place. Accounts, Monday-keyed weeks, 15-minute placement and per-day
  `missed_days` recovery are still the product model.
- Windows execution, Safari/iPhone, physical touch, full packaged flows and OS
  notification delivery remain unverified. Desktop tray reminders beyond the
  notification bridge are deferred.
- Default desktop mode uses a local database. Hosted mode uses the configured
  server; there is no automatic synchronization between them.

## Repo Landmarks
```
DESKTOP.md               PySide6 QWebEngineView recommendation + build status
desktop/origin.py        origin resolution, no Qt imports (unit-tested)
desktop/server.py        bundled uvicorn on a loopback port, no Qt imports
desktop/main.py          Qt window, persistent profile, retry panel
desktop/build_linux.sh   staged Linux build, previous artifacts preserved
desktop/build_windows.ps1 Windows standalone build preparation
desktop/tests/           origin/server tests and isolated real WebEngine probes
backend/weeks.py         week-date helpers, no framework import
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite, scrypt, hashed sessions
frontend/app.js          account lifecycle, editor, server saves
```

## Domain Model
SQLite: users → sessions, many dated weeks keyed (user_id, week_start), one
preference row. Default desktop
mode uses a local per-user database; hosted mode uses the configured deployment.
There is no automatic synchronization between those databases.

## Non-Obvious Decisions
- A week's identity is its Monday. Blocks store a day index and derive their
  date, which is why the day-index solver needed no adapter at all.
- `weeks.py` pins the ISO shape with a regex before parsing, because
  `date.fromisoformat` also accepts "20260907" and "2026-W37-1".
- The migration is guarded on the weeks table existing, since PRAGMA
  table_info returns nothing for a missing table and ALTER TABLE would raise on
  a fresh database. It runs in an explicit BEGIN IMMEDIATE, not in
  executescript, which issues an implicit COMMIT.
- Registration no longer seeds a weeks row; the NOT NULL key would reject it,
  and a missing row already means an empty week.
- GET /api/week 422s a non-Monday rather than snapping it, so a client and
  server cannot disagree about which week is open while both think they won.
- The identical-blocks short-circuit deliberately runs before the revision
  check, preserving what the pre-dated code and tests already did.
- The desktop app bundles the backend and runs it in-process (owner asked for
  this 2026-09-07). It supersedes DESKTOP.md section 1, which said not to; that
  section's reasoning was about a *second process*, which this is not.
- The loopback port is chosen by binding a socket before create_app is called,
  because the backend pins its CSRF origin check and TrustedHostMiddleware to
  one exact origin. uvicorn is handed the already-bound socket.
- uvicorn runs with loop="asyncio" and http="h11" so the build does not depend
  on uvloop/httptools surviving being frozen.
- An invalid FLEXWEEK_*_ORIGIN is an error, not a silent fall back to local:
  a typo must not quietly open a different, empty database.
- The Qt profile is parented to the QApplication, not the window: parenting it to
  the window makes Qt warn "Release of profile requested but WebEnginePage still
  not deleted" and can crash on close.
- `profile_root()` reads QStandardPaths AppDataLocation, which derives from the
  application name, so main() sets that before building the profile.
- Nuitka is called directly instead of via pyside6-deploy, which rewrites its own
  spec with absolute machine paths on every run.
- Qt translations are included; stripping them made WebEngine warn about a
  missing en-US.pak at every start.
- PySide6 6.10+ documents Python 3.14. pywebview classifiers stop at 3.13.
- Qt WebEngine cannot be statically linked; onedir Chromium libs are expected.
- No Qt WebChannel / pywebview js_api in v1 (cookies and CSRF stay on the page).
- License file is GPL-3.0. Qt for Python is LGPLv3/GPLv2/commercial.

## Session Handoff
- 2026-09-09, `feat/phase7-focus-tools`: picked up ChatGPT's uncommitted Phase 7
  work, fixed the two regressions blocking the gate (a try/except/pass in
  desktop/main.py and six mypy errors the new probe introduced), added a real
  browser case for the focus timer and alarms, and committed the lot in two
  commits. Nothing pushed.
- The editor disables every control while a save is in flight, so a click
  during that window is a visible no-op rather than a bug. A probe that does
  not wait for the save to settle will wrongly report the Add task button as
  dead; wait for `saving === false` or for the status to start with "Saved".
- Next: the remaining Phase 7 items in roadmap.md that are not yet built,
  notably splitting long blocks into pomodoro chunks on the grid, free-gap
  visualization and the block-start notification lead time.
- `spec.md` still does not document `completed_day` or any Phase 7 field. That
  contract update needs a separate approved spec edit.
- The untracked `Github Templates/` and `reslot-cac-build-plan.md` remain
  untouched.
