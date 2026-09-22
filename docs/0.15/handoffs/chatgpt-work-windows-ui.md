# Handoff: let a student say when they work (ChatGPT)

From 0.15 the planner only places homework inside work windows. The whole day is open until the
student narrows it, and nothing in the app lets them do that yet. That screen is yours: in first-run
setup, and in Settings afterwards.

## Read first

- `docs/0.15/plan.md`, decisions 3 and 5.
- `backend/models.py`, class `WorkWindow`: `days` (0 is Monday), `start` and `end` as `HH:MM` on the
  quarter hour with `24:00` allowed as an end, and an optional `subject`. Windows may overlap or
  touch; the planner merges them.
- `backend/availability.py`, `DEFAULT_WORK_WINDOWS`: what is used when a student has set none.
- `desktop/native/controller.py`, `save_availability(protected, study_windows, day_cutoff,
  work_windows)`: the one way these reach the account. Preferences come back with `work_windows`.
- `desktop/native/setup.py`: the first-run wizard. Its `HOMEWORK` page already asks how homework
  gets a time, and every page can be skipped and is remembered.
- `desktop/native/widgets.py`, `AvailabilityDialog`: how protected time and study windows are
  edited today, and the pattern to follow.
- `desktop/tests/test_setup_wizard.py` and `desktop/tests/test_ui_dialogs.py` for how these are
  tested.

## Build

    git worktree add ~/.worktrees/flexweek-015-windows -b chatgpt/0-15-work-windows feat/0.15-tabs

1. In setup, on the page about how homework gets a time, ask when the student is willing to work.
   Offer a few plain starting points, such as after school on weekdays and a wider weekend, and let
   them add their own. Skipping leaves the whole day open, and the page says so in plain words.
2. In Settings, the same editing lives with the other planning settings: add a window, remove one,
   pick its days, its start and end, and a subject if it is only for one.
3. A window is saved through `save_availability` with the rest of availability. Never write
   preferences another way.
4. Say what the student gets, not what the model holds. "Homework is only planned between these
   times." When none are set: "Homework can be planned at any time of day."
5. Accept touching and overlapping windows without complaint. Refuse only an end that is not after
   its start, and say so beside the field.

## Do not

- Do not edit `desktop/native/hours/*`, the designs, `scripts/rig/*`, `backend/*` or `spec.md`.
  The `WorkWindow` model and the planner are Grok's; if one needs changing, say so in your report.
- Do not add a second way to save preferences.
- Do not push, open a pull request, or touch the remote. Commit locally only.
- Do not touch `~/.worktrees/flexweek-phase5-*`.

## Prove it

1. Tests in `desktop/tests/test_setup_wizard.py`: the page appears, a window added there is in the
   body sent to the account, skipping it sends none, and the wording says the whole day is open.
2. Tests for the Settings side: adding, removing and editing a window reaches `save_availability`
   with the right shape, and an end before its start is refused with words next to the field.
3. `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q desktop/tests` green, and
   `.venv/bin/python scripts/verify.py` green.
4. Screenshots of both screens, in the default look and in a dark pack, read by you before you
   report. Say what you saw.

## Report back

Commit SHAs, the test names and what each proves, the screenshot paths, the exact shape you send to
`save_availability`, and anything the backend would need to change. Claude reviews before it lands.
