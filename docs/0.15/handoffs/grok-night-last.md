# Handoff: the night is the last place the planner looks (Grok)

The open day works as decided: with no work windows set, homework may go at any hour. But the
planner now reaches for midnight first whenever a session's preferred time of day is full, even with
the afternoon free. Every account that exists today has no windows, so this is what every student
gets.

## The defect

`backend/solver.py`, `_order_values`, ranks a slot by `(study, match, day, slot)`. When no slot in
the energy window is free, every other slot ties on `match`, and `(day, slot)` puts 00:00 first.
Before 0.15 the first slot of the day was 06:00, so the same tie landed on a morning.

Reproduction: lock 17:00 to 23:00 on every day, then solve one 60-minute `low` energy block allowed
on Monday to Wednesday, with no work windows.

- `248a318` (06:00 to 23:00 day): Monday 06:00.
- `e7e5206` (open day): Monday 00:00, while Monday 06:00 to 17:00 is empty.

Why the tests missed it: `test_solver.py`, `test_solver_invariants.py`, `test_completed.py` and
`test_stage4_availability.py` default to `LEGACY_WORK_WINDOWS`, so the core suites never run under
the default a real account has.

## Build

    git worktree add ~/.worktrees/flexweek-015-night -b grok/0-15-night-last feat/0.15-tabs

1. Rank night slots last. A slot is night when it starts before 06:00 or ends after 23:00. It sorts
   after every other slot the session could take, on any allowed day, but it stays a legal place:
   when nothing else fits, the night is still used (decision 5). The student's windows remain the
   only hard bound.
2. Every placement that fits inside 06:00 to 23:00 is unchanged from `248a318`. Energy, study
   windows and priority keep their current order.
3. The solver suites also run with the real default, `DEFAULT_WORK_WINDOWS`, at least for the
   invariants file, and a named test holds the reproduction above.

## Do not

- Do not change how a refusal or an explanation reads, or add a reason code.
- Do not edit `desktop/native/hours/*`, the designs, the rig, or `spec.md`. Your full-day worktree
  (`~/.worktrees/flexweek-015-fullday`) has an uncommitted `spec.md` edit; leave it uncommitted.
  Jonathan approves spec changes.
- Do not push, open a pull request, or touch the remote. Commit locally only.
- Do not touch `~/.worktrees/flexweek-phase5-*`.

## Prove it

1. The reproduction test fails on `e7e5206` and passes on your branch. Say so with the output.
2. A test that a session goes at night when 06:00 to 23:00 is full on every allowed day.
3. The busy-week timing from `context.md`, rerun: same fixture, median and maximum.
4. `.venv/bin/python scripts/verify.py` green.

## Report back

Commit SHAs, the test names and what each proves, the timing, and any existing expectation that
changed and why. Claude reviews before it lands.
