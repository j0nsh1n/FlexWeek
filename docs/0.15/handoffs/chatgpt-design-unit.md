# Handoff: put one design's Day and Week on the drag engine (ChatGPT)

Fill in `<design>` (one of timeline, mission, bento, retro, clay) and the two concept names the
owner picked. One design per run, in its own worktree. Do not start a second design in the same
worktree.

## Read first

- `docs/0.15/plan-report.md` for what 0.15 is, and `docs/0.15/plan-refined.md` if it exists.
- `docs/0.15/architecture.md` for the engine's shape and the rules it keeps.
- `desktop/native/hours/`: `geometry.py` (tracks), `hand.py` (the one gesture engine), `canvas.py`
  (`HoursCanvas`, `BlockPainter`), `chips.py` (`TrayChip`), `classic.py` (Today's app, the worked
  example to copy from).
- `desktop/native/layouts/<design>.py`, the design as it is now, and `layouts/base.py` for how a
  design renders a scene.
- `docs/0.15/mockup/index.html`, the agreed look and interaction. Open it and use
  `?design=<design>&tab=day&concept=<A or B>`. The concept's name and description are in `CONCEPTS`.

## Build

Start from `feat/0.15-tabs`:

    git worktree add ~/.worktrees/flexweek-015-<design> -b chatgpt/0-15-<design> feat/0.15-tabs

1. Day tab: `<design>`'s own Day, drawn as the picked concept, built on one or more `HoursCanvas`
   with a `BlockPainter` subclass in the design's tokens. It shows one day, a tray of homework with
   no time (`TrayChip`), and whatever else that concept's description names.
2. Week tab: the same, for the week, as the picked concept.
3. Both must offer, for the rig: `hours_surfaces()` on the view returning the visible canvases, and
   day names that open a day where the concept has them (`HoursCanvas(header=...)` does this).
4. Delete that design's old drag code as you go: its `Lift`, `Pickup`, `Zone` and drawer use, and
   set `uses_drawer = False`. No `QDrag` anywhere in the design.
5. A tray's heading leads with plain words, "No time yet" or "Not placed yet", with the themed name
   second. A student must know what the tray holds. This came from a check of the mock-up's labels.

## Do not

- Do not write gesture code. Moving, resizing, creating, placing from a tray, snapping, judging,
  auto-scroll, Escape and the held label all belong to `Hand`. If the engine cannot express your
  concept, stop and write what is missing in the report; Claude owns `desktop/native/hours/`.
- Do not edit `desktop/native/hours/*`, `scripts/rig/*`, `spec.md`, or another design.
- Do not push, open a pull request, or change anything on the remote. Commit locally only.
- Do not touch `~/.worktrees/flexweek-phase5-*`.

## Prove it

Every claim needs one of these as evidence, in your report:

1. `.venv/bin/python scripts/rig/drive.py --design <design> --tab day` and `--tab week`, both with
   every scenario PASS. The rig drives a real pointer on a hidden desktop; it never touches the
   owner's screen. Paste the summary line and the results path.
2. Open the screenshots it saves (`<design>-<scenario>-held.png` and `-end.png`) and say what you
   saw. A scenario that passes with an unreadable screen is not done.
3. `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q desktop/tests/test_layout_<design>.py`
   green, with the design's existing tests updated where the surface changed.
4. `.venv/bin/python scripts/verify.py` green (about four minutes; the pytest step has a 300 second
   budget).

## Report back

Commit SHAs, the rig summary for both tabs, the screenshot paths you read, anything the engine
could not do, and anything in the concept you had to change with the reason. Claude reviews every
design branch before it lands.
