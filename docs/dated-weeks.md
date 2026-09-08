# Contract: dated weeks

Status: proposed 2026-09-08 for Phase 5. Supersedes the spec.md line "One
current week per account initially; dated multiple weeks are a later
migration." That migration is this document.

Backend and frontend are built against this file in parallel. Neither side may
change it alone.

## Data shape

A week is identified by `(user_id, week_start)`. `week_start` is a naive local
ISO date string `YYYY-MM-DD` that is **always a Monday**. There is no time and
no timezone: the repo's time model is naive local throughout, and a week is a
calendar label, not an instant.

Blocks are unchanged. They keep `days: [0..6]` (0 = Monday) and `start: "HH:MM"`.
A block's calendar date is derived, never stored: `date = week_start + days[i]`.
This keeps the solver day-index pure and means no block rows migrate.

## Storage

```sql
CREATE TABLE weeks (
    user_id    INTEGER NOT NULL REFERENCES users(id),
    week_start TEXT    NOT NULL,                  -- 'YYYY-MM-DD', a Monday
    blocks     TEXT    NOT NULL DEFAULT '[]',
    revision   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, week_start)
);
```

`revision` is per week, not per account. Two weeks of the same account have
independent revisions.

### Migration

The old table was `weeks(user_id PRIMARY KEY, blocks, revision)`. `initialize()`
runs on every start, so the migration must be idempotent and must never lose a
row:

1. If `weeks` has no `week_start` column, rename it to `weeks_legacy`.
2. Create the new `weeks`.
3. Copy every legacy row with `week_start` = the Monday of the date the
   migration runs, preserving `blocks` and `revision`.
4. Drop `weeks_legacy` only after the copy succeeds, in the same transaction.

Running twice is a no-op. An account with no legacy row needs no work.

## API

`week_start` is chosen by the client, which knows the user's real local date.
The server only defaults when the parameter is absent.

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/week?week_start=YYYY-MM-DD` | That week for the signed-in account |
| GET | `/api/week` | The week containing the server's local today |
| PUT | `/api/week` | Save; `week_start` is required in the body |

A week that has never been saved is **not** a 404. `GET` returns it empty so the
client needs no create-or-fetch dance:

```json
{"week_start": "2026-09-07", "blocks": [], "revision": 0}
```

`PUT` body adds one field to the existing shape:

```json
{"week_start": "2026-09-07", "blocks": [...], "revision": 0}
```

`PUT` creates the row when it does not exist. Responses from both verbs carry
`week_start`, so a client can detect that it received a different week than it
asked for.

### Errors

Existing behavior is unchanged except where `week_start` is involved.

| Case | Status |
|---|---|
| `week_start` missing on PUT, malformed, or not a Monday | 422 |
| `week_start` outside 2000-01-01..2099-12-31 | 422 |
| `revision` does not match the stored revision for that week | 409 |
| Identical blocks re-saved | 200, revision unchanged, no new row |

Rejecting a non-Monday is deliberate. Silently snapping to Monday would let two
clients disagree about which week they are editing while both believe they
succeeded.

## Solver

`POST /api/solve` is unchanged. It takes blocks and returns a `SolveTrace` over
day indices. Dates never reach it. The client maps a returned day index back to
a date with `week_start + day`.

## Shared helper

Date arithmetic lives in one place, `backend/weeks.py`, with no FastAPI and no
Qt imports, matching the existing rule that `models.py` imports no framework:

- `monday_of(date_str) -> str` — the Monday of that date's week
- `current_week_start() -> str` — Monday of the server's local today
- `is_week_start(value) -> bool` — well-formed, in range, and a Monday
- `date_for_day(week_start, day_index) -> str` — the block's calendar date

The frontend needs the same four operations. It reimplements them in `app.js`
because there is no build step and no shared module, so both sides must agree
on Monday-based weeks. Frontend tests assert the same cases as the Python tests.

## Out of scope

Drag to create or move, resize, context menus, categories, copy/paste,
duplicate day, undo/redo, recurring activities, export/import, completion state
and reminders. Those are the rest of Phase 5 and land after dated weeks, per the
roadmap's own ordering.
