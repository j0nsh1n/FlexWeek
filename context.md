# context.md — FlexWeek

## Current State
- Date: 2026-09-07. Branch `feat/desktop-linux-shell` off
  `feat/desktop-packaging-recommendation`.
- Gates: `ruff check .` clean, `mypy desktop backend` clean (19 files),
  `pytest -q` 74 passed (60 backend + 14 desktop), `node --test` 8 passed.
- The Linux desktop app is self-contained as of 2026-09-07: the FastAPI backend
  runs in a background thread of the desktop process on an ephemeral loopback
  port, so no separate server is needed. Setting FLEXWEEK_DESKTOP_ORIGIN or
  FLEXWEEK_ORIGIN still points it at a hosted deployment instead.
- Source mode verified with no env origin and nothing listening: the app chose
  its own port, served itself and loaded the page.
- Session persistence confirmed at source level: register in the window, kill the
  process, reopen with the same profile -> `/api/auth/me` 200; an empty profile
  -> 401.
- Known gaps: `target=_blank` external-link path and in-page sign-out are coded
  but untested. No Windows build. Real-browser account smoke still pending.
  Partner tasks, CAC registration and district confirmation still open.
- Audit findings from 2026-09-07 are still open: `explain.py` is never imported
  so the UI shows raw reason codes; a timed-out solve reports a definite cause;
  bare-time `earliest` resolves to the wrong day.

## Repo Landmarks
```
DESKTOP.md               PySide6 QWebEngineView recommendation + build status
desktop/origin.py        origin resolution, no Qt imports (unit-tested)
desktop/server.py        bundled uvicorn on a loopback port, no Qt imports
desktop/main.py          Qt window, persistent profile, retry panel
desktop/build_linux.sh   Nuitka standalone build -> dist/FlexWeek/
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite, scrypt, hashed sessions
frontend/app.js          account lifecycle, editor, server saves
```

## Domain Model
SQLite: users → sessions, one current week, one preference row. Desktop v1 is a
webview of the hosted origin, not a second database.

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
- 2026-09-07, branch `feat/desktop-linux-shell`: built the Linux desktop
  executable, then made it self-contained by bundling the backend in-process.
  `desktop/` now holds origin.py, server.py, main.py, build_linux.sh and 20
  tests. Nothing pushed.
- Next: exercise external links and in-page sign-out against the built binary,
  then the Windows build. spec.md still describes desktop delivery without the
  bundled server and needs owner approval to update. The three audit findings
  from 2026-09-07 are still open.
