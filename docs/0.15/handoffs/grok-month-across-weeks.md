# Handoff: move a block to a date in another week (Grok)

0.15's Month tab lets a student drag a chip from one date to another. Inside the open week this is
an ordinary move. Across weeks it is not, because blocks belong to one week's document, and the
controller has no operation for it. That operation is yours.

## Read first

- `docs/0.15/plan-report.md` for the release, and `docs/0.15/architecture.md` for where this call
  is made from. The drag engine reports a change called `MoveDate(block_id, from_iso, to_iso)`;
  `NativeWindow._apply_change` in `desktop/native/window.py` will call your controller method.
- `desktop/native/controller.py`: `load_week`, `save`, `_post_pending` (a save writes a list of
  weeks), `apply_block_edit` and `move_occurrence` (how one day of a repeating block is split off),
  `place_session`, `_touch` (one Undo step), and how `pending_save` and revisions work.
- `backend/` for the week write API, including how two weeks in one save are accepted and how a
  409 conflict is reported.

## Build

On a branch from `feat/0.15-tabs`:

    git worktree add ~/.worktrees/flexweek-015-month -b grok/0-15-month-weeks feat/0.15-tabs

Add to the controller, with a name that says what a student did:

    def move_to_date(self, block_id: str, from_iso: str, to_iso: str) -> bool

Rules:

1. Same week: the block moves to that weekday, keeping its time and length. A repeating block moves
   only the day it was dragged from, as `move_occurrence` already does.
2. Another week: the block leaves the first week and appears in the second at the same time, in one
   save that writes both weeks, and as one Undo step. A repeating block still moves only that one
   day. Homework keeps its pin.
3. The second week may not be loaded. Fetch it, apply, and save both, without losing a change the
   student made meanwhile, and without a save that is half applied if the second write fails.
4. Refuse in words what the week rules already refuse: a time outside the day's hours, and homework
   that would end after it is due. Reuse `span_problem` in `desktop/native/calendar.py`; do not
   write a second rule.
5. A conflict (409) on either week leaves both untouched and says so, as saves do today.

## Do not

- Do not edit `desktop/native/hours/*`, the designs in `desktop/native/layouts/*`, or `spec.md`.
- Do not push, open a pull request, or change the remote. Commit locally only.
- Do not touch `~/.worktrees/flexweek-phase5-*`.

## Prove it

1. Controller tests in `desktop/tests/` covering: same week, across weeks forward and back, a
   repeating block moving one day only, a refusal for past due, a 409 on the second week, and Undo
   putting both weeks back. Assert on the saved weeks read back from the server, not on the
   in-memory list alone.
2. `.venv/bin/python scripts/verify.py` green.
3. A note of any backend change you needed, with the endpoint and why.

GLM is available as a helper for first-pass review. Call it through the direct OpenRouter API with
the excerpts pasted into the prompt, not through OpenCode's agent mode, which stalls on tasks that
read files. Check anything it says against the code before acting.

## Report back

Commit SHAs, the test names and what each proves, the verify summary, and the exact signature and
behaviour of `move_to_date` so the window can call it. Claude reviews before it lands.
