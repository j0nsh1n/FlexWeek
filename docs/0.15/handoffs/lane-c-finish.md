# Handoff: finish lane C, homework and planning

FlexWeek 0.15's fix round works through `docs/0.15/issues.md` in four lanes. Lane C is homework and
planning. Most of it is done and committed; an agent was stopped part-way through the last row. You
finish it. Claude reviews it before it lands.

## Where

- Worktree `~/.worktrees/flexweek-015-homework`, branch `claude/0-15-homework-planning`, from
  `8fe92c7`. Work there, on that branch. Do not merge `feat/0.15-tabs` into it; Claude merges.
- Python: `/home/jonathans/FlexWeek/.venv/bin/python` (the worktree has no venv of its own).
- Read first: `docs/0.15/issues.md` rows 6, 7, 8, 9, 24 and 35, then the five commits below
  (`git log --oneline 8fe92c7..HEAD`, and each diff).

## Done and committed

| Commit | Row | What |
| --- | --- | --- |
| `7b9d19b` | 7 | Changing the due date runs what hangs off it (the `DueField` signal no longer raises inside Qt). |
| `225908e` | 6 | New homework is due today, not on the Monday of the week on screen. |
| `8709df9` | 9 | A homework length is refused in words, from 15 minutes to 24 hours. |
| `85c5312` | 24 | The due date's calendar shows its whole month on the window's screen. |
| `e123f55` | 8 | Plan never puts homework before now. |

## To do

1. **Row 35: Plan can be undone.** Uncommitted changes are in `desktop/native/controller.py`,
   `desktop/native/window.py`, `desktop/tests/test_homework_plan.py` and
   `scripts/mutations/planner.json` (79 lines). Read `git diff`, judge whether they are complete and
   right, and finish them.
   - One press of Plan my homework is one Undo step, covering every block it placed. Replan all my
     homework is one step too. "Plan it for me as I add it" already joins its plan to the add.
   - The student can see it: a toast such as "Planned 3 homework blocks" with an Undo button, the
     same kind as the toast after finishing homework.
   - Test: Plan, then Undo, leaves the week exactly as it was; Redo puts it back. Show the test
     failing without the fix.
2. **The homework editor can show raw "Value error, …" text** for fields other than the estimate
   (it uses `_validation_text` on a pydantic error). The block editor was fixed with a table from
   field to words: `BLOCK_PROBLEMS` and `_block_problem` in `desktop/native/widgets.py` on
   `feat/0.15-tabs` (`git show feat/0.15-tabs:desktop/native/widgets.py`). Do the same for the
   homework editor so every refusal is in the app's own words, and add a test that forces each one.
3. **Screenshots.** Offscreen, of the homework editor new and with a length error, and of the due
   date's calendar open in setup and in Add homework, at 1280x860 and at 1150x768 with large text.
   Save them as `~/.flexweek-ui-harness/scratch/lane-c-*.png`, open them, and say what you see.
4. **Mutations.** `scripts/mutate.py scripts/mutations/planner.json` and `due.json` each catch every
   mutation. Include entries for the not-before-now bound and for Plan's undo step.
5. **Gate.** `scripts/verify.py`. Its pytest step has a 300-second budget that runs out at about 92%
   of the suite on this machine. If verify fails only on that budget, run `ruff check .`,
   `mypy backend` and the full `pytest -q` separately, report those, and say so. Do not edit
   `scripts/verify.py`.
6. **Records.** A line in `CHANGELOG.md` under Unreleased for anything a student notices, and rows 6,
   7, 8, 9, 24 and 35 in `docs/0.15/issues.md` marked with what was done and the commits.

## How to run things on this computer

- Run every pytest, `verify.py` and `mutate.py` through
  `~/.flexweek-ui-harness/run-alone.sh <command>`. Test suites on this computer share Qt's test
  files in `~/.qttest`, so two at once fail each other; the script waits for others to finish.
  Example:
  `QT_QPA_PLATFORM=offscreen ~/.flexweek-ui-harness/run-alone.sh /home/jonathans/FlexWeek/.venv/bin/python -m pytest -q -p no:cacheprovider desktop/tests/test_homework_plan.py`
- Offscreen Qt needs `QT_QPA_PLATFORM=offscreen`.
- Keep output under `~/.flexweek-ui-harness/scratch/`, never `/tmp`.
- No rig runs are needed for this lane.

## Do not

- Do not push, open a pull request, or change anything on the remote. Commit locally only.
- Do not launch the app without `XDG_DATA_HOME` pointing at a scratch folder. The owner's real data
  is in `~/.local/share/FlexWeek`; never open it. The owner has a test copy of the app running
  (a `desktop.main` process); leave it alone.
- Do not use `git stash`, `pkill -f` or `pgrep -f`.
- Do not touch other lanes' work: screens, words, dialogs and the other Settings pages are being
  finished in other worktrees at the same time. Stay in homework, the due field and planning.

## Report back

Commit SHAs (the five above and yours), what the uncommitted work was and what you changed in it,
each new test's failing-then-passing output trimmed to the assertion and counts, the screenshot
paths and what they show, the mutation and gate lines, and anything that looked wrong.
