# FlexWeek Architecture (Week 1)

## Ownership

| Layer | Owner | Role |
|-------|--------|------|
| Browser | UI | Week grid, sidebar, demo switcher. Fetches JSON; paints locked blocks; lists flexible tasks. **No placement solver in JS.** |
| FastAPI | Thin JSON door | Serves `frontend/` as static files and returns demo JSON. Later: accept a week payload and return a `SolveTrace`. |
| Python engine (later) | Pure / sync | Constraint placement over 15-minute slots. Must stay importable without FastAPI. Models live in `backend/models.py` with **zero** FastAPI imports. |

## Why this split

- The browser owns interaction and explanation display.
- The solver stays a pure, synchronous Python function so it is easy to unit-test and reason about.
- FastAPI is only the door: HTTP in, JSON out. It must not embed placement logic.

## Slot grid

- Monday–Sunday, 06:00–23:00 local
- 15-minute slots → 68 slots/day × 7 = **476** slots/week
- Durations must be positive multiples of 15
- Overlap helper uses half-open ranges `[start, end)`

## Week 1 deliberately omits

- `/api/solve` implementation (501 stub only)
- Any greedy/backtracking/OR-Tools/etc. placement in `frontend/app.js`
- Database / SQL

## Data flow (current)

```
demo_*.json → GET /api/demos → browser paints locked + lists flexible
```

## Data flow (later)

```
week payload → POST /api/solve → SolveTrace { placed, unplaced, moves, failed_constraints, … }
                                    ↓
                              browser explains moves
```
