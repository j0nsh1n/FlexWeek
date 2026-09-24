# FlexWeek 0.15: the working plan

This is the plan the work follows. It merges the first plan (`plan-report.md`), the review that
refined it (`plan-refined.md`, ChatGPT, branch `chatgpt/0-15-plan`) and Jonathan's decisions of
22 September. Where this file and those two disagree, this file wins.

## What 0.15 is for

Dragging in FlexWeek must feel like Daily Scheduler's: the calendar is the editor. A block follows
the pointer, either edge resizes it, dragging empty time creates one, overlaps stay usable, and the
same gestures work in every design, on Day, Week and Month. The tests must exercise the pointer path
and the saved week, because the old ones sent Qt events straight to widgets and passed while the
app was broken in use.

## Decisions (fixed)

1. Every design draws its own Day and its own Week, with real draggable hours in its own form.
2. Month follows Daily Scheduler's grid: chips carry times, a date opens Day, and dragging a chip to
   another visible date keeps the time.
3. The day is the full 24 hours, 00:00 to 24:00. (22 September, replaces 06:00 to 23:00.)
4. Hours scroll, and the student can zoom. No surface has to fit a whole day on screen.
   (22 September, replaces "Today's app Week fits without scrolling".)
5. The planner places homework only inside work windows the student sets. Until they set any, the
   whole day is open, 00:00 to 23:59. Setup asks them when they work, and Settings can change it
   later. Placing a block by hand at any hour is always allowed. (22 September.)
6. A homework's due date is required; its due time is optional, for work due at a set time that day.
   (22 September, replaces the mandatory 23:59.)
7. Time snaps to 15 minutes.
8. Overlaps are allowed, drawn side by side, and named in words.
9. Moving one day of a repeating block moves only that day.
10. Homework placed by hand is pinned, and no plan moves it.
11. A refusal leaves the block exactly where it was and says why in plain words.
12. Concepts, chosen 22 September: Timeline Column rule and Continuous scroll; Mission control Scope
    lane and Lane ops; Bento Hero clock and Hero board; Retro desktop Schedule.exe and Week.exe;
    Clay deck One big card and Fan hand, with tilt near 8 degrees. Mission and Clay fall back to
    Column watch and Table hand if their grab check fails.

## Amendments to the review

- Out-of-range drops are clamped to the track's own range, not passed to the judge as refusals. A
  block stops at the end of its track; it does not bounce with a message. Track-local bounds are
  required for partial surfaces such as Bento's part-of-day tiles.
- My day (One thing, Day dial) moves to the engine after the first two designs, not before them.
- CI installs a small window manager, as the review asked, because Escape and activation checks
  need focus to behave as it does on a desktop.
- The release gates stay at the review's bar. Windows-specific work waits until the app is built.

## How it is tested

The real-pointer rig (`scripts/rig/`) is the gate for gestures. A wait that runs out now fails the
scenario, and every result is read from the server after a marker proves the week reloaded, so a
save that never landed can no longer pass. The rig no longer falls back to the retired canvas.

Per design, the Day and Week matrix: move and snap, resize from each edge, create by drag and by
click, place from the tray, cross-day move, one day of a repeating block, overlap side by side,
refusal after due, cancel by Escape and by switching away, scroll dwell, a rebuild mid-drag, a
second move while the first save is in flight, open by tap or double click, agreement across Day,
Week and Month, and reach: at 1280x820 and 1150x768 with large text, every day and tray reachable,
a 15-minute block grabbable at 25%, 50% and 75% of its length at the default zoom.

Month adds: chips show times, a date opens Day, more than four chips stay reachable, moves within a
week and across a Sunday boundary keep the time, a drop on the source date saves nothing, an
occurrence move changes only that date, an after-due refusal restores the chip, and a failed or
conflicting save leaves exactly one chip after reload.

Also: unit tests for the engine's geometry and gestures, controller tests for every change the hand
reports, a committed mutation runner with its specs, one restart-and-reload scenario, and screenshots
read by a person against a checklist.

## Units, in order

Owners: Claude (engine, Today's app, Month UI, reviews), ChatGPT (designs), Grok (controller,
storage, CI). Each unit ends green on the rig, on the source gate, and with its screenshots read.

0. **Done.** Concepts and gates recorded, above.
1. **Rig trustworthiness.** Waits fail, reloads proven, no legacy fallback. Done 22 September.
   Today's app re-measured at 12 of 12 Day and Week scenarios under the stricter rig.
2. **The full 24-hour day.** `DAY_START_MIN` 0 and `DAY_END_MIN` 1440 through the solver, the
   controller and every surface; the planner confined to the student's work windows; existing weeks
   keep working. Owner: Grok for backend and solver, Claude for the surfaces.
   *Backend landed at `e7e5206`; audited in `audit-01.md`. Night ranked last since `36dc3ff`.*
3. **Zoom and scrolling on hours.** Pixels per hour per surface, a zoom control, a remembered level,
   and the reach checks at each level. Owner: Claude.
   *Built in `desktop/native/hours/zoom.py`. Today's app offers Day at 96, 128, 160 and 192 pixels
   an hour (15 minutes never under 24 pixels) and Week at 32, 48, 64, 96 and 128, opening at 96
   and 48. Ctrl and the wheel zoom about the pointer; Ctrl with =, - or 0 and the two corner
   buttons zoom about the middle. The level is kept per surface in the look file on this device.
   Resize zones: Daily Scheduler's 7 pixels at each end of a block 20 pixels or longer, but never
   more than a fifth of the block, so a 15-minute block moves when pressed at 25%, 50% and 75% of
   its length at every level. The rig proves both with the real pointer.*
3b. **Work windows in setup and Settings.** The screens that let a student say when they work.
   Owner: ChatGPT. Brief: `handoffs/chatgpt-work-windows-ui.md`. *Done at `66ef7c6`. Jonathan's
   call, 22 September: setup asks only for work windows; study windows stay in Settings.*
4. **Optional due times.** Due date required, due time optional, through the model, the API, the
   planner, the judge, the dialogs and the words shown. Owner: Grok for model and API, Claude for
   the dialogs. *Model, API and labels landed at `e7e5206`; the homework dialog and setup's first
   homework ask for a date and, only when ticked, a time.*
5. **Finish Today's app.** Move the 15 stale tests to the new surfaces; complete the matrix.
   Owner: Claude. *Done. The rig runs Today's app's whole Day (14) and Week (17) matrix with the
   real pointer, including 1150x768 with large text. Month's part waits for unit 9. The mutation
   runner and its specs are in `scripts/mutate.py` and `scripts/mutations/`.*
6. **The rig in CI.** Xvfb, a small window manager, per-design jobs, artifacts, timeouts.
   Owner: Grok. Brief: `handoffs/grok-rig-in-ci.md`.
7. **Hosting and targets.** Every design reaches the window's hand; the hand finds any visible
   surface; track-local bounds; render hold from press; the dial adapter. Owner: Claude.
   *Done. `Track` is a contract with `LinearTrack` and `DialTrack`; a surface is any widget with
   `takes_blocks` and `track_at`; blocks, resizes and new blocks stop at their track's own ends;
   renders are held from the press; every design is built with the window's hand and lists its
   surfaces. Proven by `desktop/tests/test_hours_targets.py` and `scripts/mutations/targets.json`.
   Month's date-aware judge moves to unit 9 with Month. `HoursScroll(axis=Axis.ACROSS)` scrolls
   and zooms lanes sideways, the plain wheel included, with day names pinned on the left: the
   horizontal zoom Mission needs, which the review asked to settle before its unit.*
8. **Cross-week MoveDate.** One atomic controller operation over two week documents, idempotent on
   retry, one Undo step. `/api/changes` already writes several weeks in one transaction.
   Owner: Grok. Brief: `handoffs/grok-month-across-weeks.md`.
   *Landed at `2d8bae3`. Undo across weeks sends the revision it last saw (`7109e3e`). Month's
   judge gives `date_problem` the chip's start, length and homework from the month reply, so a
   chip whose week is not loaded is judged by the same rule as one whose week is.*
9. **Month.** One `MonthCanvas` dressed per design, the full Month matrix. Owner: Claude.
   *Built in `desktop/native/hours/month.py`: Daily Scheduler's grid ("09:00 Title" chips, "+N
   more", a date opens Day) plus carrying a chip to another date through the one hand, with the
   date's answer shown while held. Today's app and every design use the same `MonthGrid`. Rig 9/9
   on classic. Chips for other weeks come from the month reply's per-date blocks, except in a week
   left with unsaved changes, which is drawn from those changes as the open week is.*
10. **Mission control**, then 11. **Clay deck**, 12. **Retro desktop**, 13. **Bento**,
    14. **Timeline**. One design per unit, Day and Week together, riskiest interaction first.
    Owner: ChatGPT. Brief: `handoffs/chatgpt-design-unit.md`.
15. **My day.** One thing and Day dial onto the engine. Owner: Claude.
16. **Delete the old path.** Drawer, `QDrag` helpers, the old canvas, any fallback. Owner: Claude.
17. **Docs and release evidence.** Architecture, spec (with Jonathan's approval), changelog, release
    notes, videos, supervised checks. Owner: Claude, drafts from GLM.

## Risks

- Cross-week moves can duplicate or lose work. Unit 8 before Unit 9, atomic and idempotent, no
  optimistic UI.
- The rig can aim better than a person. Reach checks at both window sizes and at the default zoom,
  plus a supervised feel check on Mission and Clay.
- A rebuild mid-drag can cancel or duplicate a change. One render hold from press, and a scenario
  that ticks the clock and lands a save while the pointer holds a block.
- Five designs can copy an engine gap ten times. CI before designs, one design per review, shared
  defects fixed in the engine with their own failing test.
- The 24-hour day widens the planner's search and allows 3am placements. Work windows bound it, and
  the solver's timing is measured in Unit 2.
- The source gate is near its 300-second budget and stalled once in a combined run. The rig runs in
  its own jobs, and the stall gets diagnosed rather than hidden.
