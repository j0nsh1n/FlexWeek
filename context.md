# context.md — FlexWeek

## Current State
- Date: 2026-09-07. Branch `feat/accounts-themes` off `docs/app-web-roadmap`.
- Phase 3 complete per owner. Phase 4 accounts/storage/themes implemented:
  registration/login/logout, account-owned SQLite weeks, revision conflicts,
  legacy import, retry/download controls and saved Nocturne/Slate preferences.
- Validation: 60 Python tests and 8 frontend state tests passed; mypy passed
  (14 source files); Python compilation, JS syntax and diff whitespace passed.
  Live HTTP smoke passed for two accounts, save/reload, solve, themes and logout.
- Changed Python files pass Ruff. Full Ruff retains pre-existing SIM110 in
  backend/solver.py:190. Existing TestClient dependency deprecation warnings remain.
- Browser verification incomplete: CUA reported no available browser. Remaining
  manual check: sign up, add/edit a block, refresh, change theme, sign out and
  sign into another account at 1280px and 390px widths.
- Known gaps: desktop packaging, calendar interaction port, later visual design
  and security hardening/audits; partner tasks and CAC registration/district.
- spec.md updated with approval. Existing untracked local files remain:
  agents.md, reslot-cac-build-plan.md, ruff.toml, Github Templates/.

## Repo Landmarks
```
backend/models.py        Pydantic blocks + bounded week validation
backend/solver.py        pure synchronous solver, existing placement unchanged
backend/app.py           account/session/ownership APIs and static frontend
backend/storage.py       SQLite transactions, scrypt, hashed sessions, throttles
backend/tests/           solver fixtures + account/API and transaction tests
frontend/app.js          account lifecycle, editor, server saves, legacy import
frontend/tests/          Node behavior tests with a simulated document
frontend/styles.css      Daily Scheduler Nocturne/Slate palette adaptation
```

## Domain Model
SQLite: users → sessions, one current week, one preference row. Weeks contain
validated TimeBlock JSON and a revision for concurrent-save detection.

```
users(id, username UNIQUE, password_hash)
  ├── sessions(token_hash, user_id, expires)
  ├── weeks(user_id PRIMARY KEY, blocks JSON, revision)
  └── preferences(user_id PRIMARY KEY, theme)
auth_attempts(key hash PRIMARY KEY, count, expires)
```

TimeBlock: locked/flexible, positive 15-minute duration, days 0–6, optional
HH:MM start and English weekday deadline. Dated multi-week storage is future work.
Default database: var/flexweek.db; FLEXWEEK_DATABASE overrides it. Browser legacy
key flexweek.week.v1 is read only for explicit import; account drafts stay in memory.

## Non-Obvious Decisions
- Solve paints a trace but does not write placements back into the saved week.
  Refresh shows the tasks the user entered; they press Solve again.
- `[hidden] { display: none !important; }` is required because `.block-form`
  uses `display: flex`, which would otherwise ignore the hidden attribute.
- Duration 10 is stopped twice: the number input's step=15, and JS before save.
  The API still 422s if something bypasses the form.
- `httpx` is in requirements.txt so FastAPI's TestClient can run API tests.
- License file is GPL-3.0. PHASES.md now links to the revised roadmap.

## Session Handoff
- 2026-09-07, `feat/accounts-themes`: approved first slice implemented and tested;
  spec, roadmap, README, architecture and changelog updated. No audits performed.
- GLM-5.3 Flash via OpenCode contributed 16 account tests and updated 3 API tests.
  Main agent read both files, corrected fixture annotations and reran all checks.
  Draft isolation mutation failed as expected, then passed after restoration.
- grok-desktop-prompt.md is ready for the independent desktop packaging decision.
- Next: real-browser smoke check, then Phase 5 desktop shell and interaction port.
  Owner selected separate desktop + web; Windows/Linux remain provisional.
- Temporary smoke servers stopped; pre-existing port-8000 development server left
  running. LitSieve source remains unavailable at ../LitSieve.
