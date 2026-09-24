# Handoff: put one design's Day and Week on the drag engine (ChatGPT)

Fill in `<design>` (one of timeline, mission, bento, retro, clay) and the two concept names the
owner picked. One design per run, in its own worktree. Do not start a second design in the same
worktree.

## Read first

- `docs/0.15/plan.md`, the working plan. `plan-report.md` and `plan-refined.md` are its history.
- `docs/0.15/architecture.md` for the engine's shape and the rules it keeps.
- `desktop/native/hours/`: `geometry.py` (the `Track` contract, `LinearTrack` and `DialTrack`),
  `hand.py` (the one gesture engine, and what a surface is), `canvas.py` (`HoursCanvas`,
  `BlockPainter`), `zoom.py` (`HoursScroll`: scrolling, zoom and a pinned header), `chips.py`
  (`TrayChip`), `classic.py` (Today's app, the worked example to copy from).
- `desktop/tests/test_hours_targets.py`: one test design that puts columns, lanes, a tilted card,
  two partial-day tiles and a dial on the same hand. It is the shortest statement of the contract.
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
3. The view is given the window's hand: accept `hand` in `__init__` and pass it on
   (`super().__init__(parent, hand=hand)`), and build every canvas and chip with `self.hand`. Never
   make a `Hand` of your own.
4. Lay time out any way the concept needs: `LinearTrack(day, area, axis, first, last, turn)` runs
   down or across, starts and ends where a tile does, and tilts for a card; `DialTrack` is round.
   Blocks stop at their own track's ends, so a part-of-day tile needs no rules of its own. Hours that
   scroll or zoom go in an `HoursScroll`, made in `render` and passed through `self.keep_zoom(...)`,
   which opens them at the level this device last chose and hands a new one to the window to keep.
   Not in `__init__`: the window gives a design the remembered levels after making it. Anything else
   a block can land on is a widget with `takes_blocks = True` and `track_at(point)`.
5. For the rig: `hours_surfaces()` already lists every visible surface; override it only if its
   order is not reading order. Day names open a day when drawn by the canvas: `header=` names days
   whose time runs down, `gutter=` names days whose time runs across.
6. Month is shared: `LayoutView.render_month` shows `MonthGrid` (`desktop/native/hours/month.py`) in
   the design's colour tokens, with chips carried by the window's hand. Keep calling it; do not draw
   a month of your own. If a concept's Month needs something the grid cannot do, say so in the report.
7. Delete that design's old drag code as you go: its `Lift`, `Pickup`, `Zone` and drawer use, and
   set `uses_drawer = False`. No `QDrag` anywhere in the design.
8. A tray's heading leads with plain words, "No time yet" or "Not placed yet", with the themed name
   second. A student must know what the tray holds. This came from a check of the mock-up's labels.
9. What Mission's review found, so it is not found again. `desktop/native/layouts/mission.py` is the
   second worked example after Today's app.
   - Make each tab's `HoursScroll` once, on its first render, and keep it; a new one every render
     loses the student's place and zoom. To keep it across `empty()`, take it out of the layout
     and hide it, but never `setParent(None)`: a widget with no parent outlives the window and
     keeps the whole view alive with it.
   - A `BlockPainter` override that draws after `super().block(...)` draws only where the painter
     drew nothing, inside `painter.save()` and `painter.restore()`. The painter writes whole,
     shortened lines on any block with room for one; it gives up under 8 px of text room.
   - The rig aims along a block's own track, so every Day and Week scenario passes on hours that
     run down, across or tilted. A failing scenario is the design's until shown otherwise.

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
   budget). Do not run it while another suite runs anywhere on this computer, in any
   checkout: they share Qt's test-mode files under `~/.qttest` and fail each other.
5. `.venv/bin/python scripts/mutate.py scripts/mutations/targets.json` still catches every break,
   which shows the shared rules were not copied into the design.

## Report back

Commit SHAs, the rig summary for both tabs, the screenshot paths you read, anything the engine
could not do, and anything in the concept you had to change with the reason. Claude reviews every
design branch before it lands.
