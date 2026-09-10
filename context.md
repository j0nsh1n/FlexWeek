# context.md — FlexWeek

## Current State
- Date: 2026-09-10. Branch `feat/rookie-ux-slice` (off `main` 652a92b), not merged.
- Rookie UX slice is in. Create account and Log in are separate screens, and
  Create account shows first. A new account gets a four-step setup (school,
  sport, first homework, Solve). Dragging or clicking the grid opens an Add
  dialog. The sidebar holds type chips. A bad day choice keeps the dialog open
  with the reason shown, basic fields come first with More options below, and
  Solve results use plain words.
- Desktop tray icon now loads in the Nuitka bundle. Close hides to the tray
  only while the icon is visible, and a second launch shows the running window.
- Gates green 2026-09-10 via `scripts/verify.py`: ruff, mypy over 22 files,
  163 Python tests (12 real WebEngine probe cases) and 86 frontend tests.
- The packaged Linux build was rebuilt to `/tmp/fw-build` (not `dist/`). With a
  throwaway profile, Plasma's StatusNotifierWatcher listed a FlexWeek item with
  22x22 icon pixmaps, and a second launch handed off and exited 0 in 0.22 s.
- Windows execution, Safari/iPhone, physical touch and OS notification
  delivery remain unverified. Close-to-tray was not clicked by hand in the
  packaged build; the probes cover it in source.
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
frontend/app.js          week state, grid, saves, solve, alarms, CATEGORIES table
frontend/editor.js       Add/Edit dialog: draft -> draftProblem -> draftPatch
frontend/setup.js        first-week setup, built on editor drafts
frontend/focus.js        focus timer, Now / Next line
frontend/auth.js         Create account / Log in screens, session start (loads last)
frontend/tests/app-scripts.mjs  loads index.html's scripts in order for DOM-stub tests
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
- Frontend scripts are classic deferred scripts sharing one global scope, not
  modules, so there is still no build step. A script's top-level code can only
  reach scripts loaded before it. The tests run them in index.html order.
- The tray icon path is anchored on the `backend` package, because Nuitka puts
  `desktop/main.py` at the bundle root as `__main__`.
- A new flexible task in the week on screen may use today onward. The solver
  does not know today's date, so without this it placed new homework on days
  already over.
- The dialog offers Fixed or Flexible only for a new item; editing keeps the
  existing kind, because converting needs completed_day and start cleanup that
  no flow asks for yet.

## Session Handoff
- 2026-09-10, `feat/rookie-ux-slice`: rookie UX slice built in eight commits
  (split, tray, auth, editor, Solve chrome, setup, docs). Nothing pushed.
- Next: owner review of the branch and a hand check of close-to-tray in the
  packaged build. Then decide on the open items below.
- Open: preferences still repeat their defaults in three places in app.js (not
  folded into a schema this slice). `spec.md` names only `frontend/app.js` and
  its syntax command, and still does not document `completed_day` or Phase 7
  fields; both need an approved spec edit.
- Two old `dist/FlexWeek` processes (started 2026-09-09) and one from
  `~/Downloads/flexweek-rookie` are still running hidden with blank tray icons.
  They were left alone. The untracked `Github Templates/` and
  `reslot-cac-build-plan.md` are untouched.
