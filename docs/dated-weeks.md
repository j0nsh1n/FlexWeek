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

Registration no longer inserts a `weeks` row. `backend/app.py` currently runs
`INSERT INTO weeks(user_id) VALUES (?)` when an account is created; under this
key that statement has no `week_start` and fails, breaking every registration.
Delete it. A missing row already means an empty week, so nothing replaces it.
The `preferences` insert beside it stays.

### Migration

The old table is `weeks(user_id INTEGER PRIMARY KEY REFERENCES users(id),
blocks TEXT, revision INTEGER)`. `initialize()` runs on every start, so the
migration must be idempotent and must never lose a row:

1. If `weeks` **exists and** has no `week_start` column, rename it to
   `weeks_legacy`. The existence check is not optional: on a fresh database
   `PRAGMA table_info('weeks')` returns no rows, so "has no week_start column"
   is trivially true, and `ALTER TABLE weeks RENAME` then raises
   `OperationalError: no such table: weeks` on every first start.
2. Create the new `weeks`.
3. Copy every legacy row with `week_start` = the Monday of the date the
   migration runs, preserving `blocks` and `revision`.
4. Drop `weeks_legacy` only after the copy succeeds.

Steps 1 to 4 run as explicit statements inside one `BEGIN IMMEDIATE` ...
`COMMIT`. They must **not** go in the existing `executescript` call:
`executescript` issues an implicit `COMMIT` first, so it cannot hold this in one
transaction, and a crash between the rename and the create would leave a
database with `weeks_legacy` and no `weeks`, failing every later request.

Running twice is a no-op. An account with no legacy row needs no work.

## API

`week_start` is chosen by the client, which knows the user's real local date.
The server only defaults when the parameter is absent.

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/week?week_start=YYYY-MM-DD` | That week for the signed-in account |
| GET | `/api/week` | The week containing the server's local today |
| GET | `/api/weeks` | `{"weeks": [...]}`, ascending, the account's saved weeks |
| PUT | `/api/week` | Save; `week_start` is required in the body |

`/api/weeks` exists so the client can navigate to weeks it did not know about.
Without it, a migrated account whose data was stamped with an earlier Monday
would open on an empty current week with nothing pointing at the real one.

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
| `week_start` on GET malformed, not a Monday, or out of range | 422 |
| `week_start` outside 2000-01-01..2099-12-31 | 422 |
| `revision` does not match the stored revision for that week | 409 |
| Identical blocks re-saved | 200, revision unchanged, no new row |
| PUT for a never-saved week with `revision` == 0 | 200, row created at revision 1 |
| PUT for a never-saved week with any other `revision` | 409 |

GET validates `week_start` the same way PUT does rather than snapping it with
`monday_of`, for the reason below: a client and a server that disagree about
which week is open must fail loudly.

**Order matters.** The identical-blocks short-circuit runs *before* the revision
check, which is what the code does today (`backend/app.py`) and what
`test_account_edges.py` pins. Re-saving identical blocks with a stale revision
returns 200, not 409. Implementing this table top to bottom would invert it.

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

The client's per-week state moves with the week. `app.js` today holds one global
`revision`, plus `dirty`, `conflict` and `suspendedDraft` that all assume a
single week. Each belongs to the week it came from, and a PUT sends the
`week_start` of the week actually on screen. A client that keeps one global
revision cannot hold two weeks and will save one week's edits over another.

## Test impact

This is a breaking API change and the existing suite records the old shape.
Both sides update their own tests in the same change:

- Backend: every exact-equality assertion on a `/api/week` response gains
  `week_start` (`test_accounts.py` has several, including
  `== {"blocks": [], "revision": 0}`), and every existing PUT body gains
  `week_start` or it now 422s. `test_accounts.py` and `test_account_edges.py`
  are both affected.
- Frontend: `accounts.test.mjs` stubs `/api/week` responses and asserts on
  `revision`, so its stubs gain `week_start`.

Update the expected values. Do not weaken an exact-equality assertion into a
subset check to make it pass.

## Out of scope

Drag to create or move, resize, context menus, categories, copy/paste,
duplicate day, undo/redo, recurring activities, export/import, completion state
and reminders. Those are the rest of Phase 5 and land after dated weeks, per the
roadmap's own ordering.
