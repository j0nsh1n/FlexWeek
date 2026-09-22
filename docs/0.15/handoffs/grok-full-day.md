# Handoff: plan the whole day, and only inside the student's work windows (Grok)

FlexWeek plans 06:00 to 23:00 today. From 0.15 a student can put something at any hour, midnight to
midnight, as Daily Scheduler allows. Opening the night up must not let the planner drop homework at
03:00, so the planner is bounded by work windows the student sets instead of by the old fixed day.

## Read first

- `docs/0.15/plan.md`, decisions 3 and 5, and the unit list. This is unit 2.
- `backend/slots.py`: `SLOT_MIN`, `DAY_START_MIN`, `DAY_END_MIN`, `SLOTS_PER_DAY`, and every helper
  built on them.
- `backend/solver.py`, `backend/availability.py`, `backend/day.py`: how the search space, free time
  and the day's shape are built from those constants.
- `desktop/native/reuse.py` and `desktop/native/controller.py`: how the client asks for a plan, and
  `settle_placements`, which decides when placed homework loses its time.
- Preferences: how `no_homework_after`, study windows and downtime are stored and reach the solver
  today (`desktop/native/setup.py` writes some of them; the API carries them).

## Build

    git worktree add ~/.worktrees/flexweek-015-fullday -b grok/0-15-full-day feat/0.15-tabs

1. The day becomes 00:00 to 24:00 everywhere the constants reach: slots, the solver, availability,
   the day summary, and anything that assumed 68 slots. Blocks may start at 00:00 and end at 24:00.
2. Work windows bound the planner. A window is a weekday, a start and an end, with an optional
   subject, and a student may have several. The planner places homework only inside them, and never
   outside, even when nothing fits. When no window is set, keep the old behaviour as the default
   window (07:00 to 22:00) so an existing account keeps working, and say so in the reply the API
   gives the client.
3. Placing or dragging a block by hand stays free at any hour. Work windows are a planner rule, not
   a calendar rule; nothing in `span_problem` changes.
4. Weeks saved before 0.15 keep working, and a homework placed by hand at 05:00 is not moved by a
   later plan.
5. Measure the solver. The search space grows by about two fifths. Record the time to plan a busy
   week before and after on the same input, and keep it within the existing limits; say what you
   measured.

## Do not

- Do not edit `desktop/native/hours/*`, the designs, the rig, or `spec.md`.
- Do not change how a refusal reads, or add new refusals. Decision 11 stands.
- Do not push, open a pull request, or touch the remote. Commit locally only.
- Do not touch `~/.worktrees/flexweek-phase5-*`.

## Prove it

1. Backend tests: a block at 00:00 and one ending at 24:00 save and load; the solver places nothing
   outside the windows; with no windows set, the default window is used; a plan on a week with a
   03:00 hand-placed block leaves it alone.
2. Controller tests: `settle_placements` keeps a hand-placed night block; a plan asked for on an old
   week still works.
3. The timing note from step 5.
4. `.venv/bin/python scripts/verify.py` green.

GLM can do a first-pass review. Call it through the direct OpenRouter API with the excerpts pasted
in, not OpenCode's agent mode, and check what it says against the code.

## Report back

Commit SHAs, the test names and what each proves, the solver timings before and after, the exact
shape of a work window as stored and as sent to the solver, and anything in the client that must
change to set them. Claude reviews before it lands.
