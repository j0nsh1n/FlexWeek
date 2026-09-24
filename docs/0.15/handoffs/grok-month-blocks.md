# Handoff: say what is on each date of a month (Grok)

0.15's Month tab draws Daily Scheduler's grid: every date shows its blocks as chips that carry their
start time ("09:00 History essay"), and a chip can be dragged to another visible date. The month
reply only counts what is on a date (`session_count`, `locked_count`), so for any week other than
the open one the client cannot draw those chips or know what a dragged chip starts at. That field is
yours.

## Read first

- `docs/0.15/plan.md`, decision 2 and unit 9.
- `backend/month.py`, `build_month`: how the grid's weeks are read and what each entry of `days`
  holds. `_placed_on_day` and `_session_pinned_on_day` already decide what is on a date.
- `backend/tests/test_month_api.py` for how the reply is tested.
- `desktop/native/controller.py`, `move_to_date` and `date_problem`: the client will call them with
  what this field says.

## Build

On a branch from `feat/0.15-tabs`:

    git worktree add ~/.worktrees/flexweek-015-monthblocks -b grok/0-15-month-blocks feat/0.15-tabs

1. Each entry of `days` gains `blocks`: every block that has a time on that date, whatever its kind,
   in start order and then by title. Each is:

       {"id", "title", "start", "duration_min", "category", "kind", "assignment_id",
        "repeats", "pinned", "completed"}

   `start` is `HH:MM`, `assignment_id` is null for anything that is not homework, and `repeats` is
   true when the block sits on more than one day of its week (so moving it moves one date only).
2. A block on several days of a week appears on each of those dates, with the same `id`.
3. Homework that has no time yet is not in `blocks`; it stays where it is today.
4. The existing fields keep their meaning. Nothing else in the reply changes.
5. Keep the reply's size sane: a full month of a busy student (5 blocks a day) must stay well under
   the API's response habits. Say what you measured.

## Do not

- Do not edit `desktop/native/*`, `scripts/rig/*` or `spec.md`. Claude builds the Month tab on this.
- Do not push, open a pull request, or touch the remote. Commit locally only.
- Do not run `scripts/verify.py` while another suite or an OpenCode session runs anywhere on this
  computer, in any checkout: they share Qt's test-mode files under `~/.qttest`.

## Prove it

1. Month API tests: a repeating block appears on each of its dates with `repeats` true; homework
   pinned at a time appears on its date with its `assignment_id`; homework without a time does not;
   a block on the last Sunday of the grid and one on the first Monday of the next month's weeks are
   both on the right dates; the order within a date.
2. `.venv/bin/python scripts/verify.py` green.

## Report back

Commit SHAs, the test names and what each proves, the exact shape of one `blocks` entry, and the
reply size you measured. Claude reviews before it lands.
