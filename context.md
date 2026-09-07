# context.md — FlexWeek

## Current State
- Date: 2026-09-06. Branch `feat/phase-3-usable` off `feat/phase-2-solver`.
- Phase 3 code exit is green locally: `pytest -q` 40 passed. Browser: new week
  → add locked school + homework → Solve → refresh still shows that week.
  Garbage in localStorage reloads Alex instead of crashing. Duration 10 is
  rejected in the form and as HTTP 422 on `POST /api/solve`.
- Known gaps:
  - Partner bug list (Phase 3), break-it cases (Phase 2), interviews (Phase 1).
  - CAC registration and congressional district confirmation.
  - `spec.md` still describes the dataclass / 501-stub skeleton and was not
    edited.
  - Untracked on purpose: `agents.md`, `reslot-cac-build-plan.md`, `spec.md`,
    `ruff.toml`, `Github Templates/`.

## Repo Landmarks
```
backend/models.py        Pydantic TimeBlock; duration must be a multiple of 15
backend/solver.py        backtracking + MRV + forward checking, 150 ms cap
backend/app.py           GET /api/demos/{name}, POST /api/solve
backend/tests/           slots, demos, solver, api (40 cases)
frontend/index.html      forms: add locked, add task, new week
frontend/app.js          editor + localStorage key flexweek.week.v1
```

## Domain Model
No database. Demo weeks are JSON on disk. The user's week lives in
`localStorage` as `{ blocks: TimeBlock[] }`.

```
TimeBlock
  kind        locked | flexible
  duration_min  positive multiple of 15
  days        [0..6]
  start       HH:MM for locked; solver fills flexible
  latest      English "Friday 21:00" for flexible
```

## Non-Obvious Decisions
- Solve paints a trace but does not write placements back into the saved week.
  Refresh shows the tasks the user entered; they press Solve again.
- `[hidden] { display: none !important; }` is required because `.block-form`
  uses `display: flex`, which would otherwise ignore the hidden attribute.
- Duration 10 is stopped twice: the number input's step=15, and JS before save.
  The API still 422s if something bypasses the form.
- `httpx` is in requirements.txt so FastAPI's TestClient can run API tests.
- License file is GPL-3.0. PHASES.md Phase 6 still says MIT.

## Session Handoff
- 2026-09-06, branch `feat/phase-3-usable`: forms, localStorage, 422 on bad
  duration, T8 corrupt-storage reset. 40 tests green.
- Next: Phase 4 priority/energy explain panel, or partner unsupervised tests.
