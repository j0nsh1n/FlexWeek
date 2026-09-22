# FlexWeek 0.15 plan: report for review

## What FlexWeek is

FlexWeek is a desktop homework planner for high-school students, written in Python with PySide6
(Qt 6) and a local FastAPI backend that runs inside the app. It ships for Windows and Linux; the
current release is 0.14.3. A student sees their week (school, sports, homework), and a planner
places homework around fixed commitments before each deadline. The app has six "designs", which
are whole-app layouts, not colour themes: Today's app (a plain calendar), Timeline (editorial),
Mission control (dark HUD with day lanes), Bento (rounded tiles), Retro desktop (Windows 95 windows)
and Clay deck (pastel cards fanned like a hand). Every design has Day, Week and Month tabs. Two more
screens, One thing and Day dial, are "My day" screens for living the day rather than planning it.

## Why 0.15

The owner, Jonathan, compared FlexWeek with his other app, Daily Scheduler, and found FlexWeek's
dragging much worse. His words: the tabs should be "more in line with how Daily Scheduler does it",
the designs "don't allow proper dragging, especially on today", and "testing isn't thorough enough".
He asked for a significant overhaul for 0.15.

What a side-by-side comparison showed:

- Daily Scheduler's Day tab is its main editing surface: one full-width timeline at 96 px an hour.
  You drag a block and it follows the pointer in 5-minute steps, a block's top or bottom edge
  resizes it, dragging empty time creates a block, and blocks that overlap sit side by side. Its
  Week tab is an overview where the whole day fits without scrolling. Its Month tab is a grid of
  days with "08:00 School" chips; a click opens that day.
- FlexWeek's Day tab in Today's app was a plain list with nothing to drag. In the five other
  designs the Day tab showed the same screen as Week. FlexWeek's Month was cut off at the top,
  repeated unplaced homework on every day and showed no times; Retro's month drew broken cells.
- Dragging in the designs used the operating system's drag-and-drop, with a side drawer of hours
  sliding in. Behaviour differs between Wayland and X11, and it is the path the tests could not see.
- Every drag test sent Qt events straight to widgets. A real pointer was never used. The first
  real-pointer test found drops landing 15 minutes early, because the hours scrolled every time
  the pointer passed through their edge.

## What the owner decided

1. Each design draws its own Day tab (not one shared widget): real, draggable hours in that
   design's own form.
2. Every design's Week tab gets real draggable hours too, still in its own form.
3. Today's app's Week is an overview that fits the whole day without scrolling (Daily Scheduler's
   week), and blocks can still be dragged and resized on it.
4. Month is Daily Scheduler's month grid, plus dragging a chip to another date moves the block
   there at the same time.

Rules carried over from earlier releases: 15-minute snap; two blocks at one time are allowed and
drawn side by side, each marked; dragging one day of a repeating block (Wednesday's School) moves
only that day; homework placed by hand is pinned so no plan moves it; a drop is refused only
outside the day's hours (06:00 to 23:00) or when homework would end after it is due, and the
refusal is said in words.

Still open: for each of the five designs, which of two concepts for Day and which of two for Week.
A clickable mock-up and a walkthrough video exist; Jonathan has not picked yet. Recommendations:

| Design | Day, recommended / other | Week, recommended / other |
|---|---|---|
| Timeline | Column rule: one ruled column under the big day heading, homework without a time in the right margin / Ledger spread: the clock-ordered list on the left page, an hour rail on the right | Continuous scroll: each day a heading with its hours across beside it / Timetable: days as columns, hours as rows |
| Mission control | Scope lane: one wide horizontal lane under a magnified ruler / Altitude tape: hours down a vertical tape | Lane ops: seven horizontal day lanes, fully live / Column watch: transposed to columns |
| Bento | Hero clock: the big hero tile becomes the day's timeline / Part-of-day tiles: Morning, Afternoon, Evening tiles | Hero board: seven columns in one big tile / Day tiles: a wall of eight tiles |
| Retro desktop | Schedule.exe: one window with the day's hours / Wallpaper day: the desktop itself is the day | Week.exe grid / Seven windows, one per day |
| Clay deck | One big card with hour grooves / Felt board with clay cards | Fan hand: the fanned cards, tilt eased to about 8 degrees / Table hand: cards laid flat in a row |

## Design of the shared engine

"Each design draws its own" applies to the look and layout. The gestures are shared, so a drag
behaves the same everywhere and is tested once. The pieces, all in `desktop/native/hours/`:

- `geometry.py`. A track is one day's stretch of minutes inside a painted widget: a rectangle,
  which way time runs (down a column or across a lane), the first and last minute, and an optional
  turn in degrees for a card laid at an angle. It converts between points and minutes, both ways.
  Also 15-minute snapping and the side-by-side column layout for overlaps. Pure arithmetic.
- `hand.py`. The one gesture engine, owned by the window. Anything that can be picked up calls
  `hand.press(source, held, point)`. The hand then follows the pointer through an application-level
  event filter (so it survives the pressed widget being rebuilt, and sees Escape wherever focus is),
  waits for a real drag, finds the hours under the pointer, snaps, asks the window's one rule,
  draws the result in place with the times written on the block, scrolls a scroll area only after
  the pointer rests 300 ms at its edge, and on release reports one change: Move, Place, Create or
  MoveDate. A press that never becomes a drag is a tap.
- `canvas.py`. `HoursCanvas` is one painted widget holding any number of tracks (a day, seven
  columns, seven lanes, a turned card). A design supplies where the tracks lie and a `BlockPainter`
  subclass for how things look; it never writes gesture code. The canvas also answers the test rig
  in screen coordinates: where a day and minute are, where a block is drawn, how to scroll a
  stretch of hours into view.
- `chips.py`. `TrayChip` is homework with no time, dragged from a tray onto any hours; a click
  still opens it.
- Planned: `month.py` with `MonthCanvas`, the painted month that also takes chip drags.

No system drag-and-drop anywhere in the new code, so Wayland and X11 behave alike and the rig's
real-pointer tests match what a student sees. The window's judge is still the single rule for
what can go where.

## How it is tested

- A real-pointer rig (`scripts/rig/`). It starts KWin on a virtual screen with its own Xwayland,
  runs FlexWeek there as an X11 client, and moves that display's pointer with xdotool, so presses,
  moves and releases take the path a mouse's do, without touching the owner's desktop. Each
  scenario seeds the same week with the clock at Thursday 15:40, performs one gesture, waits for
  the save, reloads the week from the server and asserts on it. It saves screenshots mid-drag and
  after the drop, and a video per design. 15 scenarios per design across Day, Week and Month.
- Baseline on 0.14.3: Today's app 6 of 15; Timeline, Mission control, Bento, Retro desktop and
  Clay deck 0 of 14 each.
- Unit tests of the geometry and the gesture engine, and mutation checks (break one rule, the
  named test must fail).
- Helpers the owner asked for throughout: GLM-5.3-Flash (through OpenCode) for divergent ideas,
  first-pass reviews and doc checks; Jev (a TypeSafe classifier) for per-item judgments such as
  whether each tray label tells a student what it holds. Their findings are checked before use.
  So far GLM supplied the design concepts and a design review (7 findings: one real bug, one rule
  worth keeping, five already handled); Jev flagged five themed tray names ("Cargo bay", "In the
  dish") as unclear, so trays will lead with plain words.

## Where things are

- `desktop/native/hours/`: the engine. `geometry.py` (tracks and snapping), `hand.py` (the one
  gesture engine), `canvas.py` (`HoursCanvas` and `BlockPainter`), `chips.py` (`TrayChip`),
  `classic.py` (Today's app's Day and Week, the worked example).
- `desktop/native/window.py`: owns the `Hand`, turns its changes into saves (`_apply_change`), and
  holds the one rule (`_judge_span`).
- `scripts/rig/`: the real-pointer rig. `hidden_session.py` starts the hidden desktop,
  `drive.py` holds the scenarios.
- `desktop/tests/test_hours_geometry.py` and `test_hours_hand.py`: the engine's unit tests.
- `docs/0.15/architecture.md`: the engine's shape, its alternatives, and a review's findings.
- `docs/0.15/mockup/index.html`: the clickable mock-up of every concept, with a working drag.
  `check_mockup.py` beside it screenshots and drag-checks all 28 surfaces.
- `docs/0.15/handoffs/`: the briefs for each agent.

## Status on 22 September 2026

Done, on a local branch, nothing pushed:

- The rig and the 0.14.3 baseline.
- The clickable mock-up of every concept, drag-checked on all 28 surfaces, and a walkthrough video.
- The engine (geometry, hand, canvas, tray chip) with unit and mutation tests.
- Today's app's Day (Daily Scheduler's day with a Not placed yet tray and a summary) and Week (fits
  06:00 to 23:00, day names open the day) on the engine. The rig passes all 12 Day and Week
  scenarios for Today's app with a real pointer.

Not done: 15 older tests still expect the retired week canvas and Day list, and fail fast on
`window.week_table.body` or `window.day_agenda`; Month; the five designs; the Day screens; docs,
spec and release. One combined test run stalled once when several window test files ran together
under a `-k` filter, while the full suite finished in about three and a half minutes. Worth
watching when the migration lands.

## Proposed work plan

Each unit ends with its rig scenarios green with a real pointer, its screenshots read, the
unit tests green, and the full test gate green.

1. Finish Today's app: move the 15 older tests to the new surfaces. Owner: Claude.
1b. Design hosting: give every design access to the window's `Hand` and a default
   `hours_surfaces()`, so a design can build hours without touching the engine. This blocks every
   design unit. Owner: Claude.
2. Month: `MonthCanvas` for every design, chips with times, click opens the day, drag a chip to
   another date within the loaded week. Owner: Claude.
3. Moving a block to a date in another week from Month. Blocks belong to one week's document, so
   this needs a controller operation that writes two weeks in one save. Owner: Grok, brief in
   `docs/0.15/handoffs/grok-month-across-weeks.md`.
4. The rig in CI: an Xvfb mode so GitHub's Linux runner can run the real-pointer scenarios on every
   pull request. Owner: Grok, brief in `docs/0.15/handoffs/grok-rig-in-ci.md`.
5. to 9. One design at a time on the engine, with the concepts Jonathan picks: Timeline, Mission
   control, Bento, Retro desktop, Clay deck. Owner: ChatGPT, one worktree per design, brief in
   `docs/0.15/handoffs/chatgpt-design-unit.md`. Claude reviews each against its rig scenarios and
   screenshots.
10. My day screens (One thing, Day dial) onto the engine, then delete the old drawer and every
    remaining use of system drag-and-drop. Owner: Claude.
11. Docs, the spec's dragging section (the owner approves spec edits), changelog, release notes.
    Draft: GLM. Review: Claude.
12. Release 0.15 on the owner's word, with the rig video attached to the pull request.

## Risks and open questions

- Month moves across weeks (unit 3) touch how weeks are stored. Should 0.15 ship Month drags only
  within the open week, with other dates refused in words, if unit 3 is not ready?
- Native Wayland input cannot be driven in the rig without taking over the owner's real pointer.
  The engine avoids platform drag-and-drop so X11 results should hold on Wayland; one supervised
  run on the owner's desktop before release would confirm it.
- Tilted cards (Clay's fan) make small blocks harder to grab. The mock-up drags work, but it needs
  a feel check.
- Five designs, each with two new surfaces, is the largest part of the work. Should any design ship
  its new Day in 0.15 and its new Week in 0.15.1, to release sooner?
- Keyboard and screen-reader access to moving a block is not in scope yet. Should 0.15 add keyboard
  moves (arrow keys by 15 minutes) on the new surfaces?
- The test gate has a 300-second budget and was at about 245 seconds. The new tests and rig must not
  push it over; the rig runs separately and in CI.
