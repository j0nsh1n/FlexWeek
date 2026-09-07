# context.md — FlexWeek

## Current State
- Date: 2026-09-06. Branch `feat/phase-1-skeleton` off `25daf25` (origin/main).
- Phase 1 code exit is green locally: `pytest -q` 15 passed. `GET /` 200,
  `/api/demos/alex` and `/jordan` each return 4 locked + 8 flexible,
  unknown demo 404, logo and favicon 200.
- FastAPI stub `POST /api/solve` still returns the identity placement
  (locked stay, flexible unplaced). That is the Phase 1 stub, not the
  real solver.
- GLM-5.3 Flash is reachable as `opencode run -m openrouter/z-ai/glm-5.3-flash`.
  It drafted the demo JSON and extra demo tests; those files were reviewed
  and the 23:00 slot rule was re-tested red-then-green by the main agent.
- Known gaps:
  - Partner checkboxes in PHASES.md (real interviews, pitch in their words).
  - CAC registration and congressional district confirmation.
  - `spec.md` still describes the older dataclass / 501-stub skeleton and
    was not edited this session.
  - `Github Templates/ci.yml` is uninstalled and still names pyright.
  - Untracked on purpose for now: `agents.md`, `reslot-cac-build-plan.md`,
    `spec.md`, `ruff.toml`, `Github Templates/`.

## Repo Landmarks
```
backend/models.py        Pydantic TimeBlock / Move / SolveTrace
backend/slots.py         HH:MM grid helpers; overlaps is half-open
backend/solver.py        Phase 1 stub (locked stay, flexible unplaced)
backend/explain.py       reason code → English (Phase 4 copy)
backend/app.py           FastAPI door: static, /api/demos/{name}, /api/solve
backend/data/demo_*.json anonymized weeks (12 blocks each, 8 flexible)
backend/tests/           test_slots.py + test_demos.py (15 cases)
frontend/                index.html, styles.css, app.js, logo.png, favicon.png
PHASES.md                contest calendar
FlexWeek.png             source poster the logo was cropped from
```

## Domain Model
No database. Demo weeks are JSON arrays of TimeBlock on disk.

```
TimeBlock
  id, title, course
  kind        locked | flexible
  duration_min  positive multiple of 15
  days        [0..6]  (0 = Monday)
  priority    1 test | 2 quiz | 3 homework | 4 reading
  energy      high | medium | low
  earliest / latest   latest is English like "Thursday 21:00" in Phase 1
  start       HH:MM for locked; filled later for flexible

SolveTrace
  placed, unplaced, moves, failed_constraints, solve_ms, complete
```
Grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week.

## Non-Obvious Decisions
- Origin `25daf25` rewrote Week 1 onto Pydantic + HH:MM (no calendar dates
  on `start`). Local `892d241` used dataclasses and `YYYY-MM-DDTHH:mm`.
  This session fast-forwarded to origin and finished Phase 1 on that model.
- Sleep is a locked 22:00–23:00 "Sleep guard" on every day, not a hidden
  23:00–06:00 interval — those hours are outside the grid.
- `latest` in the demos is still an English string. Phase 2 will need a
  parseable deadline.
- Logo crop is the phone + dumbbell from `FlexWeek.png`; the poster text
  is not in the topbar.
- License file is GPL-3.0. PHASES.md Phase 6 still says MIT.
- Dependabot is off. CI templates stay uninstalled.

## Session Handoff
- 2026-09-06, branch `feat/phase-1-skeleton`: logo in the UI, partner-style
  demos with 8 flexible tasks each, grid CSS tightened, 23:00 rejected as a
  start, stale `test_models.py` removed, 15 tests green.
- Next: Phase 2 `backend/solver.py` — backtracking + MRV + forward checking,
  empty / packed / impossible fixtures. Do not start until the human says
  Phase 1 partner work is done or to proceed anyway.
