# Handoff: two things the cross-week move review found (Grok)

`move_to_date` landed on `feat/0.15-tabs` and works: one write of both weeks, retry-safe, nothing on
screen until the server accepts it. Claude's review found two gaps in the code and one in the tests.
The test gap is already closed (`test_a_move_into_a_week_that_already_has_blocks_keeps_them`). The
two code gaps are yours.

## Read first

- `desktop/native/controller.py`: `date_problem`, `_block_on_week`, `_commit_move_to_date`,
  `_post_travel_weeks`, and the `ok` path of `_post_pending` that fills a step's `after`.
- `desktop/tests/test_logic_move_date.py`, the tests you wrote, and the one added at the end.

## Build

On a branch from `feat/0.15-tabs` (at the commit that has this file, or later):

    git worktree add ~/.worktrees/flexweek-015-move2 -b grok/0-15-move-date-2 feat/0.15-tabs

1. **Undo across weeks must not overwrite a week changed elsewhere.** `_post_travel_weeks` fetches
   the other week and writes it with whatever revision it finds, so a change made to that week on
   another device, or by anything not on this undo stack, is silently replaced by the snapshot. Keep
   the revision the move last saw for each week in the step (`_pending_step["weeks"][i]["revision"]`,
   filled from the reply the same way `after` is), send that as the expected revision, and refresh it
   after each undo and redo. A mismatch is a 409, said the way saves say it, with both weeks untouched.
2. **`date_problem` must answer for a chip whose week is not loaded.** It returns None, meaning "no
   problem", when `_block_on_week` finds nothing, so the Month tab would show a chip as droppable and
   then refuse it after the fetch. Month knows the chip's start and length from the month reply. Take
   an optional `start: str | None = None, duration_min: int | None = None` (or a small record) and
   judge from those when the week is not local. Return None only when the answer is truly "fine".

## Do not

- Do not edit `desktop/native/hours/*`, the designs, the rig, or `spec.md`.
- Do not push, open a pull request, or touch the remote. Commit locally only.
- Do not run `scripts/verify.py` while another suite or an OpenCode session runs anywhere on this
  computer, in any checkout: they share Qt's test-mode files under `~/.qttest`.

## Prove it

1. A test where the other week changes (a second save to it with the session, after the move and
   outside the undo stack) and Undo of the move is then refused with a 409 and both weeks kept.
2. A test that `date_problem` refuses a past-due chip for a week the session has not loaded, given
   its start and length, and passes a fine one.
3. `.venv/bin/python scripts/mutate.py scripts/mutations/planner.json` still catches every break.
4. `.venv/bin/python scripts/verify.py` green.

## Report back

Commit SHAs, the test names and what each proves, and the final signature of `date_problem`.
Claude reviews before it lands.
