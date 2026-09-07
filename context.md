# context.md — FlexWeek

## Current State
- Date: 2026-09-07. Branch `feat/desktop-packaging-recommendation` off
  `feat/accounts-themes`.
- Phase 4 accounts/storage/themes already on the parent branch (60 Python tests,
  8 frontend tests). This slice is the desktop packaging recommendation only:
  `DESKTOP.md`. `grok-desktop-prompt.md` was deleted after the write-up.
- No desktop code or installer was added. No UI redesign or security audit.
- Known gaps: real-browser smoke for accounts; Phase 5 shell implementation;
  partner tasks; CAC registration/district.

## Repo Landmarks
```
DESKTOP.md               PySide6 QWebEngineView recommendation + checklist
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite, scrypt, hashed sessions
frontend/app.js          account lifecycle, editor, server saves
```

## Domain Model
SQLite: users → sessions, one current week, one preference row. Desktop v1 is a
webview of the hosted origin, not a second database.

## Non-Obvious Decisions
- Desktop v1 loads the hosted origin; it does not start a local FastAPI.
- PySide6 6.10+ documents Python 3.14. pywebview classifiers stop at 3.13.
- Qt WebEngine cannot be statically linked; onedir Chromium libs are expected.
- No Qt WebChannel / pywebview js_api in v1 (cookies and CSRF stay on the page).
- License file is GPL-3.0. Qt for Python is LGPLv3/GPLv2/commercial.

## Session Handoff
- 2026-09-07: desktop packaging recommendation written from official Qt and
  pywebview docs; prompt file removed. Next: owner accept DESKTOP.md, then
  Phase 5 `desktop/main.py`, or the pending real-browser account smoke check.
  spec.md still says shell selection is Phase 5 implementation — flag if the
  owner wants PySide6 named in the spec.
