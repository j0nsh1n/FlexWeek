# context.md — FlexWeek

## Current State
- Date: 2026-09-10. Branch `feat/hybrid-frost` off `main` 3a8d3a6 (v0.8.0
  first-open packaging merged via PRs #4-#6). Not pushed.
- Hybrid frost visual system is in: one token map per theme in
  `frontend/styles.css` (`:root` = nocturne/dark, `[data-theme="slate"]` =
  light), frosted chrome with a solid fallback, near-opaque week grid, soft blue
  accent, Figtree font and a duotone SVG icon sprite in `index.html`.
- Gates green 2026-09-10 via `scripts/verify.py`: ruff, mypy over 22 files,
  184 Python tests (real WebEngine probes, now checking the Figtree face loads
  and signed-out pages start light) and 95 frontend tests.
- Windows execution on a real PC, Safari/iPhone, physical touch and OS
  notification delivery remain unverified. Hosted web URL is not online.
- Default desktop mode uses a local database. Hosted mode uses the configured
  server; there is no automatic synchronization between them.

## Repo Landmarks
```
docs/cac-build-plan.md   original Sep 6 contest brief (working title Reslot)
.github/workflows/       verify.yml (mypy), codeql.yml, release packages
DESKTOP.md               PySide6 QWebEngineView recommendation + build status
desktop/origin.py        origin resolution, no Qt imports (unit-tested)
desktop/server.py        bundled uvicorn on a loopback port, no Qt imports
desktop/main.py          Qt window, persistent profile, retry panel
desktop/build_linux.sh   staged Linux build, previous artifacts preserved
desktop/package_linux.sh release tar.gz with README, icon and .desktop
desktop/check_bundle.py  glibc and missing-library check, no Qt imports
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
frontend/styles.css      both theme token maps, then components that only read tokens
frontend/fonts/          Figtree variable font + OFL license, served from /static
frontend/tests/theme-tokens.test.mjs  token parity, no raw colors, no-blur contrast, accent vs categories
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
- Windows ICU (icuuc/icuin) is a system DLL since 1703. Copying it out of
  System32 would redistribute Microsoft's files; the bundle check requires the
  import to be satisfied by Windows 10 1809+ instead.
- Theme stays the `nocturne|slate` API enum; menus only relabel it Dark/Light.
  Signed-out HTML and `signedOut()` use slate; the saved theme applies after
  login, and new accounts still default to nocturne per spec.md.
- Frost alphas are chosen so text passes WCAG AA composited straight over the
  page gradient with no blur; that is the case Qt WebEngine hits when blur is
  not drawn. The theme-tokens test computes it, so do not lower an alpha without
  rerunning it.
- The accent must stay at least CIE76 distance 15 from every category color
  (School blue is the near miss), enforced by the same test.
- Icons are an inline `<symbol>` sprite, not a file: `<use>` inherits
  `--icon-secondary` into the symbol only when the sprite is in the page.
- Linux ships a tar.gz rather than an AppImage so the executable bit survives
  and no extra runtime is required. Unused Qt `.qm` files are dropped; the
  Chromium en-US locale pack stays.

## Session Handoff
- 2026-09-10, `feat/hybrid-frost`: token maps, frosted chrome, grid tokens,
  Light/Dark labels, slate signed-out default, Figtree, duotone icons, theme
  token tests and CHANGELOG. Before/after screenshots were taken offscreen in
  /tmp/fw-frost (not committed). Nothing pushed.
- Next: owner review of both themes on a real screen, then decide whether new
  accounts should default to light (needs a spec.md change).
- Open: hosted web URL, a hand check of close-to-tray and of the Windows zip
  on a real PC.
