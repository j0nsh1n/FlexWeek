# context.md — FlexWeek

## Current State
- Date: 2026-09-07. Branch `feat/desktop-completion` off `feat/desktop-linux-shell`.
- Phase 4 complete: real Qt WebEngine tests exercise register, editor save,
  Solve, reload, theme persistence, sign-out and two-account isolation at
  1280px/390px. Rendered layouts inspected at both widths.
- Gates: Ruff clean, mypy desktop/backend clean (23 files), 84 Python tests and
  8 frontend state tests passed; Python compilation and Bash syntax passed.
- Rebuilt dist/FlexWeek/FlexWeek, preserving the old artifact as a dated sibling.
  Packaged HTTP smoke passed: bundled server/frontend, account, save, solve,
  reload, sign-out, with temporary data and no virtualenv/PYTHONPATH.
- Fixed external-popup page retention and missing draft-download handling.
  Real WebEngine tests cover both; OS browser handoff is intercepted in tests.
- Windows build script drafted by GLM-5.3 Flash and corrected by the main
  agent for staging/publication, explicit MSVC and environment restoration.
  No Windows/PowerShell runtime is available; execution remains unverified.
- Phase 5 calendar interaction work remains. The existing explanation/timeout/
  bare-earliest findings remain for scheduled solver/explanation work; no new
  audit was performed. Partner/CAC tasks remain outstanding.
- spec.md drift remains: bundled-server behavior and concrete PySide6 build
  details are not recorded there. Spec content left unchanged this session.

## Repo Landmarks
```
DESKTOP.md               PySide6 QWebEngineView recommendation + build status
desktop/origin.py        origin resolution, no Qt imports (unit-tested)
desktop/server.py        bundled uvicorn on a loopback port, no Qt imports
desktop/main.py          Qt window, persistent profile, retry panel
desktop/build_linux.sh   staged Linux build, previous artifacts preserved
desktop/build_windows.ps1 Windows standalone build preparation
desktop/tests/           origin/server tests and isolated real WebEngine probes
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite, scrypt, hashed sessions
frontend/app.js          account lifecycle, editor, server saves
```

## Domain Model
SQLite: users → sessions, one current week, one preference row. Default desktop
mode uses a local per-user database; hosted mode uses the configured deployment.
There is no automatic synchronization between those databases.

## Non-Obvious Decisions
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
- 2026-09-07, `feat/desktop-completion`: completed Phase 4 verification, fixed
  desktop popup/download gaps, rebuilt Linux, prepared Windows packaging.
- Next planned work: Windows build and execution on a Windows host; Phase 5
  dated calendar storage/navigation, then direct editing and the other listed
  interactions. Additional Daily Scheduler scope remains deferred per owner.
- GLM's additional review attempt timed out; the main agent completed the
  script review and corrections. Windows limitations are in DESKTOP.md.
  No new dependencies were installed.
- Temporary test apps used isolated profiles/databases; the original Linux
  artifact was preserved. Nothing pushed.
