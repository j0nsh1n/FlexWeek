# context.md — FlexWeek

## Current State
- Date: 2026-09-11. v0.9.1 is released (PR #8, tag at b06f897). Branch
  `feat/windows-installers` off that merge, for v0.9.2.
  `feat/frost-reference-look` (5ca38b7, restyle after the owner's reference
  dashboards) is parked and in neither release.
- 0.9.1 shipped: a page renderer that stops reopens solved and solid instead of
  a blank window; `--smoke-test` walks setup to its Solve with a pixel check;
  the AppImage `.sha256` names only the file; AppImage FUSE doc tip.
- 0.9.2 in progress: Windows installers (`FlexWeek-Windows-x64-Setup.exe`,
  `FlexWeek-Windows-x64.msi`) replace the zip, whose shortcut pointed at the
  build machine. Installers are only built and run on the GitHub Windows runner.
- The owner sees flicker in the setup dialog on Windows and is investigating
  that directly. On the owner's Linux PC (KDE Wayland, RX 9070, Mesa 26.2.2) blur on,
  blur off and GPU off all looked the same, with no flicker.
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
frontend/theme.js        System/Light/Dark choice -> data-theme, loaded in <head>
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
- Windows installers: the Inno `AppId` and the MSI `UpgradeCode` are fixed
  forever, since upgrades find the installed copy by them. The .exe is per
  account (`PrivilegesRequired=lowest`) for students; the .msi is per machine
  for school IT. Inno Setup is not on windows-latest, so CI downloads 7.1.0 and
  checks its SHA-256. WiX is pinned to 6.0.2 because v7 blocks every command
  until someone accepts its EULA.
- Windows ICU (icuuc/icuin) is a system DLL since 1703. Copying it out of
  System32 would redistribute Microsoft's files; the bundle check requires the
  import to be satisfied by Windows 10 1809+ instead.
- `theme` is `system|slate|nocturne` (default `system`, owner decision
  2026-09-10). CSS only knows slate and nocturne on `<html data-theme>`;
  `frontend/theme.js` runs in `<head>` so first paint already matches the
  device, and re-resolves on device changes only while the choice is system.
  Signed-out screens always follow the device.
- SQLite cannot alter a CHECK, so `allow_system_theme()` rebuilds an older
  preferences table once in one transaction; stored slate/nocturne are kept.
- Offscreen Qt ignores `setColorScheme`; the `system_dark` probe forces a dark
  device with `--blink-settings=preferredColorScheme=0`. A real KDE dark
  session does reach `prefers-color-scheme: dark`.
- Frost alphas are chosen so text passes WCAG AA composited straight over the
  page gradient with no blur; that is the case Qt WebEngine hits when blur is
  not drawn. The theme-tokens test computes it, so do not lower an alpha without
  rerunning it.
- The accent must stay at least CIE76 distance 15 from every category color
  (School blue is the near miss), enforced by the same test.
- Icons are an inline `<symbol>` sprite, not a file: `<use>` inherits
  `--icon-secondary` into the symbol only when the sprite is in the page.
- Linux leads with a tar.gz so the executable bit survives and no extra runtime
  is required. The AppImage ships too, but needs FUSE (libfuse2); without it
  the docs say `--appimage-extract` then `squashfs-root/AppRun`, or the tarball.
  Unused Qt `.qm` files are dropped; the Chromium en-US locale pack stays.
- A dead page renderer leaves Qt's view one flat near-white color, and a lost
  GPU context leaves it the page background color; neither reaches the page or
  shows a dialog. A GPU-process crash kills the whole app instead (Qt runs GPU
  in-process). Hence `renderProcessTerminated` recovery in `desktop/main.py` and
  the smoke's window-grab color count (a blank page is 1 color, the bare page
  gradient under 100, a solved week 400 or more on an 8 px grid).
- The 0.9.0 blank window was not reproduced on: source offscreen, the published
  v0.9.0 Linux build on Xvfb/llvmpipe with GPU compositing, tray and
  notifications on, accessibility on, or eight clock times across the week.
  Trigger still unknown; likely GPU/driver specific (0.9.0 added the only
  backdrop-filter rules) or Windows.
- Smoke runs use a temporary data folder. WebEngine writes profile files until
  its page and profile are destroyed, so `MainWindow.discard()` runs before the
  folder is removed, or empty cache folders come back.

## Session Handoff
- 2026-09-11, `feat/windows-installers`: Inno Setup and WiX scripts in
  `packaging/windows/`, workflow builds, installs, shortcut-checks, smokes and
  uninstalls both; pull requests touching packaging run it without uploading.
  Docs and `desktop/tests/test_windows_installers.py` updated. Release notes in
  `docs/release-notes-v0.9.2.md`.
- Open: spec.md still names `FlexWeek-Windows-x64.zip` (downloads list and the
  Definition of Done); owner approval needed to change it.
- 2026-09-11, `fix/0.9.1`: renderer recovery (shell reload with
  `?recovered=1`, solid panels, re-Solve, native panel on a repeat), extended
  smoke with pixel check and throwaway data, WebEngine `recovery` probe,
  basename AppImage checksum plus workflow check, AppImage FUSE and Windows
  shortcut doc lines, release notes in `docs/release-notes-v0.9.1.md`.
- v0.9.1 released and marked latest after CI smoke passed on all three builds.
- 2026-09-10, `feat/hybrid-frost`: token maps, frosted chrome, grid tokens,
  Light/Dark labels, slate signed-out default, Figtree, duotone icons, theme
  token tests and CHANGELOG. Before/after screenshots were taken offscreen in
  /tmp/fw-frost (not committed). Nothing pushed.
- Theme defaults to System per the owner's spec change (same day): API,
  storage migration, theme.js, menus and probes updated.
- Next: owner review of both themes on a real screen.
- Open: hosted web URL, a hand check of close-to-tray and of the Windows zip
  on a real PC.
