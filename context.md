# context.md — FlexWeek

## Current State
- Date: 2026-09-07. Branch `feat/desktop-linux-shell` off
  `feat/desktop-packaging-recommendation`.
- Gates: `ruff check .` clean, `mypy desktop backend` clean (19 files),
  `pytest -q` 74 passed (60 backend + 14 desktop), `node --test` 8 passed.
- The Linux desktop shell is built and runs: `dist/FlexWeek/FlexWeek`, onedir,
  453 MB with a 33 MB launcher. Confirmed under `env -i` with no Python present:
  it fetched `/`, the static assets, and `/api/auth/me` from a live server.
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
- Desktop v1 loads the hosted origin; it does not start a local FastAPI.
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
- 2026-09-07, branch `feat/desktop-linux-shell`: built the first Linux desktop
  executable (PySide6 QWebEngineView shell + Nuitka standalone), added
  `desktop/` with 14 unit tests, `requirements-desktop.txt`, and the build
  script. Fixed a pre-existing ruff SIM110 so the branch passes its own gate.
  Nothing pushed.
- Next: exercise external links and in-page sign-out against the built binary,
  then the Windows build. The open audit findings are unaddressed.
