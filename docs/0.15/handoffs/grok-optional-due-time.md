# Handoff: a due time is optional (Grok)

Homework carries a due date and a time, and the time is always there, usually 23:59 because nothing
asked for it. From 0.15 the date stays required and the time is optional, for work that really is
due at a set time that day, such as a lesson at 09:00.

## Read first

- `docs/0.15/plan.md`, decision 6. This is unit 4.
- `backend/models.py` and `backend/assignments.py`: how `due` is stored, validated and returned.
- `backend/solver.py` and `backend/slots.py`: how a deadline bounds where a session may go.
- `desktop/native/calendar.py`: `due_point`, `sunday_due`, `due_day_in_week`, `span_problem`, and
  `desktop/native/weekmodel.py`: `due_label` and the slack wording.
- `desktop/native/widgets.py`: the homework dialog's due field, and `desktop/native/setup.py`, which
  sets a due date during setup.

## Build

    git worktree add ~/.worktrees/flexweek-015-due -b grok/0-15-optional-due feat/0.15-tabs

1. A stored due value is either a date, `2026-09-27`, or a date and time, `2026-09-27T09:00`. Both
   are accepted by the API; everything that reads `due` handles both.
2. A date-only due means the end of that day. Homework may be planned anywhere on that date, and a
   placement that ends within that day is never refused as after its due time.
3. A due with a time keeps today's behaviour: work must end by it.
4. Words a student reads stay plain. A date-only deadline reads "due Sun 27 Sep"; with a time it
   reads "due Sun 27 Sep, 09:00". Keep one function for this, `due_label`, so no screen invents its
   own wording.
5. Existing homework keeps working. A stored `...T23:59` still means the end of that day and must
   not start reading as a hard 23:59 deadline where it did not before.

## Do not

- Do not edit `desktop/native/hours/*`, the designs, or the rig.
- Do not change the dialogs' layout; Claude owns the frontend. Say what the dialog needs and Claude
  will build it. The model, the API, the solver and the shared date helpers are yours.
- Do not edit `spec.md`. Do not push or open a pull request. Commit locally only.

## Prove it

1. Backend tests: a date-only due saves, loads and bounds the solver at the end of that day; a due
   with a time bounds it at that minute; an old `T23:59` value keeps its meaning.
2. Tests for `due_point` and `span_problem` covering both shapes, including a block that ends at
   23:45 on the due date (allowed for date-only) and one that ends at 09:15 against a 09:00 due
   time (refused, with the existing words).
3. `due_label` tests for both shapes.
4. `.venv/bin/python scripts/verify.py` green.

## Report back

Commit SHAs, the test names, the exact accepted shapes of `due`, and the list of client places that
still assume a time is present, so Claude can finish the dialogs. Claude reviews before it lands.
