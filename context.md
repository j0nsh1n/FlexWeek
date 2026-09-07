# context.md — FlexWeek

## Current State
- Date: 2026-09-06. Branch `feat/phase-2-solver` off `feat/phase-1-skeleton`.
- Phase 2 code exit is green locally: `pytest -q` 37 passed. Packed fixture
  and both demos solve in ~1–2 ms. `POST /api/solve` returns a SolveTrace.
- Browser: Alex and Jordan Solve place all 8 flexible tasks; debug panel
  shows `solve_ms`, placed 8, unplaced 0, complete.
- Known gaps:
  - Partner break-it cases (Phase 2), interviews/pitch (Phase 1).
  - CAC registration and congressional district confirmation.
  - `spec.md` still describes the dataclass / 501-stub skeleton and was not
    edited. The running app is Pydantic + HH:MM + a real solver.
  - Untracked on purpose: `agents.md`, `reslot-cac-build-plan.md`, `spec.md`,
    `ruff.toml`, `Github Templates/`.

## Repo Landmarks
```
backend/models.py        Pydantic TimeBlock / Move / SolveTrace
backend/slots.py         HH:MM grid helpers, deadline parse, occupancy masks
backend/solver.py        backtracking + MRV + forward checking, 150 ms cap
backend/explain.py       reason code → English (Phase 4 copy)
backend/app.py           FastAPI door: static, /api/demos/{name}, POST /api/solve
backend/data/demo_*.json anonymized weeks (12 blocks each, 8 flexible)
backend/tests/           test_slots.py + test_demos.py + test_solver.py (37)
frontend/                grid, Solve button, debug panel
PHASES.md                contest calendar
```

## Domain Model
No database. Demo weeks are JSON arrays of TimeBlock on disk.

```
TimeBlock
  kind        locked | flexible
  duration_min  positive multiple of 15
  days        [0..6]  (0 = Monday)
  priority    1 test | 2 quiz | 3 homework | 4 reading
  energy      high | medium | low
  latest      English "Thursday 21:00" or "HH:MM" (last allowed day)
  start       HH:MM; locked is given, flexible filled by the solver

SolveTrace
  placed, unplaced, moves, failed_constraints, solve_ms, complete
```
Grid: Mon–Sun 06:00–23:00, 15-minute slots, 68/day × 7 = 476/week.

## Non-Obvious Decisions
- Deadlines are English weekday + time because Phase 1 demos shipped that
  way. `parse_deadline` must not split on the letter T inside "Thursday".
- A flexible block must finish by `latest` (end ≤ deadline), not merely start
  before it. Sleep is the grid edge: nothing starts at 23:00 or runs past it.
- Search: MRV, then higher priority (lower number), then earlier deadline.
  Energy is only a sort on values (morning / afternoon / evening).
- First Solve does not emit moves for successful placements. Unplaced blocks
  get a Move with the reason code so the debug panel can name them.
- License file is GPL-3.0. PHASES.md Phase 6 still says MIT.

## Session Handoff
- 2026-09-06, branch `feat/phase-2-solver`: solver v1, 37 tests, Solve + debug
  panel. Both seed demos complete under 3 ms.
- Next: Phase 3 forms + localStorage, or partner break-it cases on this solver.
