# context.md — FlexWeek

## Current State
- Date: 2026-09-08. Branch `feat/phase5-calendar-interactions`.
- Phase 6 scheduling behavior is implemented: backend-authored explanations,
  deadline slack badges, click-to-highlight, and per-occurrence missed-lock
  recovery with cross-day move details and restore.
- Phase 5 slices D/F/B/E are in: occurrence vs series locked edits, reminder
  preferences with web/in-app alerts, category chips (incl. sleep), week/day
  export-import, and per-block completed. Desktop tray reminders deferred.
- Gates green: 110 Python tests (+5 skipped), 31 frontend behavior tests and
  JavaScript syntax. The real-WebEngine case covers
  solve, slack, miss, cross-day replan, save, reload and restore.
- A missed occurrence is stored as one day in a locked block's `missed_days`.
  It is excluded from solver occupancy without deleting the block or its other
  weekday occurrences. Recovery uses the existing `/api/solve` endpoint and
  saves through the normal revision-checked week write.
- Dated weeks are done. Weeks are keyed `(user_id, week_start)` where
  week_start is a naive local ISO Monday. Blocks keep their day index and
  derive their date, so no block data moved and the solver is untouched.
- The migration was proven against the real desktop database, not a fixture: a
  copy of `~/.local/share/FlexWeek/flexweek.db` kept its "School" block
  byte-identical at revision 4 under week_start 2026-09-07, running
  `initialize()` twice changed nothing, and the app then served that week,
  created a second week, and left the first untouched.
- Phase 5 slices A/D/F/B/E are in. Still open: copy/paste, duplicate day,
  undo/redo, Windows build execution, desktop tray reminders.
- Windows build remains prepared but unexecuted; no Windows host here.
- `dist/FlexWeek` was rebuilt 2026-09-08 against the merged code and verified:
  the packaged binary registers an account, reads and writes dated weeks, lists
  them via /api/weeks, and 422s a non-Monday. Released as
  `dist/FlexWeek-linux-x86_64-20260908.tar.gz` (205 MB compressed) with a
  .sha256 beside it; both are gitignored on purpose. See DESKTOP.md section 8.
- `dist/` grows by roughly 528 MB per rebuild because build_linux.sh preserves
  each previous build and never prunes. It holds three copies as of today.
- Databases carrying the old schema were backed up to
  /tmp/fw-db-backup-20260908-081624 before any migration ran.

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
- `date_for_day` in weeks.py has no Python caller. It is kept as the tested
  reference the JS mirror in app.js is checked against.
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
- 2026-09-08, `feat/phase5-calendar-interactions`: Phase 5 slices D→F→B→E on top
  of slice A. Occurrence/series locked edits, reminder prefs + web/in-app alerts,
  category chips, export/import, completed flag. 110 pytest (+5 skip), 31
  frontend tests, `node --check` clean. Pushed to origin feature branch.
- Next: Phase 5 leftovers (copy/paste, duplicate day, undo/redo, Windows build,
  optional tray) or Phase 6 deployment persistence.
- Settled 2026-09-08 by the owner: dated weeks + desktop build in spec; Phase 7
  committed; agents.md tracked. Built app is a release asset, not committed.
- Still undecided: whether `Github Templates/` and `reslot-cac-build-plan.md`
  get committed.
