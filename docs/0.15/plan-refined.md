# FlexWeek 0.15 refined implementation plan

## What FlexWeek is

FlexWeek is a local-first desktop homework planner for high-school students. It is written in
Python with PySide6 and runs its local FastAPI backend inside the application. The current release
is 0.14.3 for Linux and Windows.

A student gives FlexWeek their classes, fixed commitments, homework and due dates. The planner
places homework into the available time. The application has six designs: Today's app, Timeline,
Mission control, Bento, Retro desktop and Clay deck. These are complete layouts rather than colour
themes. Each has Day, Week and Month tabs. One thing and Day dial are separate My day screens for
doing the current work.

The 0.15 work must serve a student who does not know FlexWeek's storage model or implementation.
Ordinary actions must be visible, reversible before release, and described in everyday words. The
implementation should preserve the project's existing philosophy: one source of truth for shared
behaviour, pure calculation where possible, explicit state changes at the boundary, and no second
gesture system hidden inside an individual design.

## Why 0.15

Daily Scheduler makes the calendar itself the main editor. A block follows the pointer, either edge
resizes it, dragging empty time creates a block, overlaps remain usable, Week shows the whole day,
and Month uses time-labelled chips. FlexWeek 0.14.3 does not provide that experience consistently.
Today's app Day is a list, the other designs reuse Week for Day, Month is hard to read, and several
layouts depend on operating-system drag-and-drop plus a temporary hours drawer.

The existing tests also give more confidence than the application has earned. They send Qt events
directly to widgets and usually begin at a calculated centre point. A student does not know the
perfect point to press. The first real-pointer check already found a visible defect: merely passing
through a scroll edge shifted a drop by 15 minutes.

Version 0.15 therefore has two inseparable outcomes:

1. Day, Week and Month behave like dependable calendar editors in all six designs.
2. The tests exercise the same pointer path and persistence boundaries that a student uses.

Visual variety remains valuable, but it cannot change what a gesture means. A themed label may
follow a plain label; it may not replace one. A green test is insufficient if a 15-minute block is
too small to grab, a refusal is only a colour, or a normal Month move fails because the destination
belongs to a different internal week document.

## What the owner decided

These decisions are fixed for 0.15:

1. Every design draws its own Day tab with draggable hours in that design's visual language.
2. Every design draws its own Week tab with draggable hours in that design's visual language.
3. Today's app Week fits 06:00 to 23:00 without scrolling and still supports moving and resizing.
4. Month follows Daily Scheduler's month grid. Its chips include their times, a date opens Day, and
   moving a chip to another visible date keeps its local start time.
5. Time snaps to 15-minute boundaries.
6. Overlaps are allowed, drawn side by side, and identified in words.
7. Moving one occurrence of a repeating block affects only that occurrence.
8. Homework placed by hand is pinned so a later plan cannot move it.
9. A drop is refused only outside 06:00 to 23:00 or when homework would end after its due time. A
   refusal leaves the original untouched and explains the reason in words.

One Day concept and one Week concept still need an owner decision for each of the five themed
designs. Implementation should use one chosen concept, not build both. The recommended starting
set is:

| Design | Day | Week | Reason |
|---|---|---|---|
| Timeline | Column rule | Continuous scroll | It keeps Timeline's editorial identity while leaving one obvious time axis. |
| Mission control | Scope lane | Lane ops | It makes Mission the deliberate test of horizontal time and compressed lanes. |
| Bento | Hero clock | Hero board | It keeps the large tile as the clear primary editing surface. |
| Retro desktop | Schedule.exe | Week.exe | One window per task is unnecessary complexity; one schedule window is easier to understand. |
| Clay deck | One big card | Fan hand | The fan preserves Clay's identity if tilt and target-size checks pass. |

The concept choice is the only product gate before design work. If Clay's Fan hand cannot provide
a reliable target at 1150 pixels wide with tilt capped near 8 degrees, use Table hand. If Mission's
Lane ops cannot keep labels and 15-minute targets usable at that width, use Column watch. That is a
fallback decided by a named usability check, not a late aesthetic rewrite.

### Scope boundary

Version 0.15 includes the fixed decisions, cross-week Month moves, a real-pointer CI gate, migration
of the existing My day drag consumers, and deletion of the old drawer and system drag-and-drop path.
Keeping My day on the old mechanism would leave two definitions of dragging and prevent the cleanup
that makes later changes safe.

The following do not block 0.15:

- Arrow-key moving and resizing in 15-minute steps. Target 0.15.1. Version 0.15 still requires
  keyboard focus, a literal accessible name for each occurrence, Enter to open, Escape to cancel,
  and a keyboard-reachable form that can edit the same day and time. A parallel accessible schedule
  list is acceptable if painted occurrences cannot be useful Qt accessibility children.
- Automated native-Wayland pointer control. Keep one supervised native-Wayland release check and
  investigate safe automation after 0.15.
- Unselected Day and Week concepts. Keep them as design references; do not promise them for 0.15.1.
- Decorative animation and polish that does not improve clarity, target size or feedback.

Day or Week for any design, cross-week Month behaviour, save safety, clear refusal feedback and the
shared gesture architecture are not valid scope cuts. If cross-week movement cannot be made safe,
defer Month chip dragging as a complete feature rather than expose invisible week boundaries.

## Design of the shared engine

The design owns tracks, painting and surrounding layout. The window owns one `Hand`, one placement
judge and the controller operations that persist changes. This boundary keeps each design distinct
without making six subtly different editors.

The current pieces in `desktop/native/hours/` are:

- `geometry.py`: pure conversion between screen points and minutes, track direction and rotation,
  15-minute snapping, spans, and side-by-side overlap geometry.
- `hand.py`: the application-level gesture state machine for move, resize, create, tray placement
  and date movement. It owns the drag threshold, implicit grab, Escape handling, render hold and
  300 ms scroll-edge dwell.
- `canvas.py`: `HoursCanvas`, hit testing, painting hooks, test coordinates and the contract for
  revealing a time or block.
- `chips.py`: unplaced homework chips that can be opened or placed onto hours.
- `classic.py`: Today's app Day and Week, the reference implementation.
- Planned `month.py`: the shared Month grid and its themed painter inputs.

The target abstraction is not finished. `Track` is currently an alias of rectangular
`LinearTrack`, `Hand` only searches `HoursCanvas`, and the rig chooses the first visible hours
surface. Before Month, themed layouts or My day migrate, the contract must support a list of
rectangular canvases and an explicit adapter for Day dial. It must locate a target by point and a
visible day label by day without assuming that time runs down. Track intervals are half-open and
their own first/last bounds, rather than global bounds, control creation and resizing. This is
needed for partial-day Bento surfaces as well as the dial and Clay's multiple cards.

The architecture document's older `session.py` name must be corrected to `hand.py` when docs are
updated. New layout code must not create another hand, duplicate snapping, judge a drop, save a
placement, or use `QDrag`. It may provide one or more `HoursCanvas` instances and implement how
their tracks and blocks look.

`Hand` reports a typed change; it does not write storage. The window/controller applies that change
through one operation. A Month move across a Monday-keyed week boundary is one atomic domain
operation even though it changes two week documents. It must:

- remove one source occurrence and add one destination occurrence together;
- preserve the local start time, duration, assignment link, pin state and logical identity;
- leave unrelated placements semantically unchanged;
- make a retry idempotent; and
- leave the source unchanged on validation, revision conflict or write failure.

The backend already accepts several weeks in one `ChangesRequest` transaction, and the controller
already has multi-week fetch/write machinery. The Month operation should extend those boundaries
rather than invent another persistence route. It still needs deliberate completion behaviour: stay
on the same month, refresh both affected weeks, and avoid navigating to an arbitrary written week.
The operation records one history step for both weeks. Undo runs the reverse atomic operation, and
the step becomes stale if either week reloads at another revision before undo. It does not inherit
the current single-open-week assumption.

Month also needs an occurrence payload before it needs a canvas. Counts and total minutes cannot
draw or move `19:00 History essay`. Define one occurrence record with the source week, stable block
or occurrence identity, date, title, category, start, duration, assignment/series identity, pin and
completion fields needed to preserve the item.

Keep the controller's existing occurrence rule for 0.15. Moving one repeated day removes that
weekday from the source series and creates one standalone block for the moved day. The new block
keeps the title, category, assignment link and other user data. The remaining occurrences keep
their original dates and times. Acceptance tests assert those visible results rather than the
internal shape alone.

The UI must not optimistically show a completed cross-week move until that operation succeeds. On
failure it restores the source chip and gives a plain explanation. The same judge enforces hours
and due dates for Day, Week and Month. The hand must pass an out-of-range candidate to that judge;
clamping it into 06:00 to 23:00 would make the required outside-hours refusal unreachable.
The current `Judge` has no date argument and `MoveDate` bypasses it. Extend the contract with a
date-target judgment that receives the block, source date and target date. Month calls it while the
chip is held and uses the same `Verdict.words` path before release.

A single render hold starts on press, before the drag threshold, and covers the complete gesture. A
timer tick, save completion, tab refresh or other rebuild may update unrelated UI, but cannot delete
the source widget, change the held block or commit twice. Only the latest queued scene is rendered
after the gesture. Switching tab, design, account or week during a held gesture cancels it without
a save.

## How it is tested

Testing is divided by the kind of failure it can prove. Pixel-perfect screenshots and direct Qt
events are not substitutes for persisted outcomes.

### Pure and widget tests

Geometry tests cover vertical, horizontal and rotated tracks; points just inside and outside a
track; 06:00 and 23:00; all four directions around a 15-minute snap boundary; minimum duration;
overlap columns; and non-overlapping inverse conversions. `Hand` tests cover the transition from a
tap to a drag, both resize edges, Escape, render hold, dwell timing, lost targets and exactly one
commit.

Widget tests call public surface contracts rather than retired children such as `week_table.body`
or `day_agenda`. Tests tied only to those private widgets are deleted. Behaviour tests are retained
and rewritten to assert a visible state or a persisted result.

### Controller and storage tests

Controller tests exercise move, resize, create, place and MoveDate through the same application
boundary as the window. Cross-week tests use two Monday-keyed documents and cover success, exact
due-time acceptance, one-step-past-due refusal, a stale revision on either week, transaction
rollback, and retry after an unknown response with the same operation ID. Each case asserts that
the block exists exactly once and that unrelated placements did not change. A repeating placement
test proves that the moved occurrence keeps its user data while every other occurrence keeps its
original date and time.

### Real-pointer rig

The rig drives an actual pointer, reloads the saved week, and checks literal expected dates and
times. It also inspects public geometry and visible words. Scenarios use ordinary points within the
hit area as well as calculated centres. Every scenario has a timeout, a named failure message and
screenshots for the held and final states. A failed busy wait, save wait or reload is an immediate
failure. The rig must confirm a fresh server load before reading results; it may not fall back to a
mutated in-memory block. Scenario reset clears selection, history, scroll and held state as well as
seeded blocks.

The shared Day and Week matrix for every design is:

| Scenario | Required evidence |
|---|---|
| Move and snap | An off-grid pointer move persists the expected 15-minute start with no initial jump. |
| Resize start and end | Each edge persists the expected start and duration; neither can cross the other or leave 06:00-23:00. |
| Create | Dragging empty time creates exactly one block; a short click performs the documented quick action instead. |
| Place | A `Not placed yet` chip lands at the expected time, is pinned, and disappears from the tray after reload. |
| Cross-day Week move | The same block moves to the target day and expected snapped time. |
| Repeating occurrence | The chosen occurrence moves and keeps its title, category and assignment link; every other occurrence keeps its original date and time after reload. |
| Overlap | Both saved blocks remain, their rectangles are distinct and side by side, and visible text identifies the conflict. |
| Refusal | Out-of-hours and after-due drops keep the exact original and show the shared plain-language reason. |
| Cancel | Escape, release outside all hours, lost grab, or a tab/design switch saves nothing. |
| Scroll dwell | Passing through an edge does not scroll; holding for at least 300 ms scrolls; the final saved minute matches the post-scroll pointer. |
| Rebuild during drag | A minute tick and a completed unrelated save do not cancel, duplicate or offset the held operation. |
| Rapid second move | A second move released while the first save is pending uses the returned revision in order; a fresh load contains one block at the second move's final position. |
| Open | A tap or double click, as defined by the surface, opens the intended item without starting a drag. |
| Cross-view agreement | A change made in Day appears once with the same date and time in Week and Month after each view reloads. |
| Fit and reach | At 1280x820 and 1150x768 with large text, every day and tray remains reachable. A scrollable Day renders 15 minutes at no less than 24 pixels. A whole-day Week block can start a move from deterministic points at 25%, 50% and 75% of its visible length, with no dead zone or resize-edge theft. |

Month adds these scenarios:

- chips show a time, a date click opens that Day, and overflow beyond four chips remains reachable;
- movement within a week and across a Sunday/Monday boundary preserves the local time;
- movement onto an adjacent-month cell that is visible in the grid works;
- dropping on the source date is a no-op and sends no save;
- an occurrence move changes only that date;
- after-due refusal restores the source chip and says why; and
- a failed or conflicting cross-week save leaves exactly one source chip after reload.

The rig gains a `settled(week_start)` equivalent that loads any Monday-keyed document. A cross-week
scenario confirms the fresh destination document, then reloads and confirms the source. Checking
only the currently open week cannot prove that a move created exactly one destination occurrence.

One persistence scenario closes and recreates the window/controller against the same database after
a saved move, signs back in, and verifies the same occurrence in Day, Week and Month. This proves
storage rather than the lifetime of one in-memory session.

Screenshots are evidence with a review checklist, not decoration. For each completed design they
cover empty state, held state, accepted state, refused state, overlap and a full tray at both tested
window sizes. A reviewer checks legible times, untruncated plain labels, visible focus, target reach,
contrast in light and dark modes where supported, and the absence of clipped controls. The CI job
retains screenshots and `results.json`. Walkthrough videos run locally for release evidence instead
of increasing every CI job's time and storage.

### CI and supervised platform checks

The real-pointer job moves into CI before themed layouts are added. It begins with Today's app and
adds a design to the required matrix in the same change that implements that design. There are no
expected failures and no fallback to the retired widgets. Jobs are split by design so the normal
source gate remains under its 300-second budget and a single failure has a useful artifact.

CI uses Xvfb/X11 and proves that path only. Before 0.15 is released, a person runs the core move,
resize, create, cross-day, cross-week Month and refusal checks on native Wayland and on Windows.
Those checks record application version, display scale, window size and outcome. They do not require
a release build until the owner asks for one.

The complete release evidence is:

- source gate green: Ruff, mypy, pytest and the repository verification script;
- controller/storage tests green;
- every shipped design's rig matrix green with retained screenshots and `results.json`;
- local walkthrough videos for every shipped design;
- three consecutive clean rig runs after the final engine change; and
- supervised Wayland and Windows checks recorded without a data-loss or input blocker.

## Where things are

- `desktop/native/hours/`: shared geometry, hand, canvas, chip and classic surfaces.
- `desktop/native/window.py`: the window-owned `Hand`, the one placement judge, surface hosting and
  controller dispatch.
- `desktop/native/widgets.py` and existing layout modules: remaining old drawer and system
  drag-and-drop consumers to migrate and then delete.
- `scripts/rig/drive.py`: scenario definitions, gestures, persisted assertions and screenshots.
- `scripts/rig/hidden_session.py`: the isolated compositor/display used by the local rig.
- `desktop/tests/test_hours_geometry.py` and `desktop/tests/test_hours_hand.py`: engine tests.
- `docs/0.15/architecture.md`: engine design, alternatives and prior review findings.
- `docs/0.15/mockup/index.html`: the 28 concept surfaces. It is design evidence, not the production
  gesture contract.
- `docs/0.15/handoffs/`: bounded implementation and review briefs.

The final cleanup includes an `rg` check for `QDrag`, the old hours drawer, legacy canvas entry
points and rig fallbacks. Any remaining match must be unrelated framework code with an explicit
reason; no shipped planning or My day surface may depend on the old path.

## Status on 22 September 2026

The local `feat/0.15-tabs` checkpoint contains:

- the real-pointer rig and a recorded 0.14.3 baseline;
- the clickable concept mock-up and its 28-surface drag check;
- shared geometry, hand, canvas and tray-chip code with focused engine tests; and
- Today's app Day and Week on the engine, with the current 12 Day and Week pointer scenarios green.

Still incomplete:

- 15 older tests refer to the retired Week canvas or Day list;
- the design-hosting contract is not finished;
- Month and its atomic cross-week MoveDate operation do not exist;
- the five themed designs and the two My day screens are not on the new engine;
- the rig is not a required CI matrix and lacks the failure cases listed above;
- old system drag-and-drop and drawer code remains; and
- architecture, spec, changelog and release notes have known drift.

The first report claims mutation checks, but this checkpoint has no rerunnable mutation script or
recorded command. Treat mutation coverage as unproven until a named artifact exists; ordinary tests
must carry the release gate meanwhile.

A combined test selection stalled once, while a full run completed in about 245 seconds. Treat that
as an unresolved reliability signal. Diagnose it while moving the rig into its own jobs; do not hide
it by raising the source-gate budget.

No implementation work, build or release is part of this planning pass.

## Proposed work plan

Each unit is small enough to review on its own and leaves the branch in a verifiable state. A design
unit contains Day and Week together. If a design exposes an engine defect, fix the shared engine in
a separate unit with a failing behaviour test before resuming design work.

### Unit 0: lock concepts and the release contract

Record the selected Day and Week concept for all five themed designs. The table above is the
recommendation. Freeze the common scenario matrix, shared refusal wording and 1150x768 usability
size. Record two density rules: a scrollable Day uses at least 96 pixels per hour, while a Week that
fits 06:00 to 23:00 must accept a move at 25%, 50% and 75% of a 15-minute block's visible length.
Record the resize-zone policy and the Mission horizontal zoom policy before implementation.

Done when:

- one concept per design is recorded with no unresolved A/B implementation;
- the owner-visible behaviour matches the fixed decisions;
- every rig scenario has a stable name, seed, action and persisted or visible predicate; and
- Mission and Clay have their named fallback condition.

### Unit 1: stabilize Today's app and the source-test baseline

Audit the 15 stale tests. Retain user behaviour and remove assertions that exist only for retired
private widgets. Extend Today's app from its current 12 scenarios to the complete common Day and
Week matrix.

Done when:

- no test references `window.week_table.body` or `window.day_agenda`;
- no Today's app rig path falls back to a legacy widget;
- Today's app passes the complete matrix at both required sizes;
- an accessibility-tree test finds each occurrence by a literal title, day, start, end and status;
  keyboard focus reaches the schedule or its parallel list, Enter opens the editor, and the editor
  can change and save day and time without a pointer; and
- the full source gate completes within 300 seconds on three consecutive runs, or the stall has a
  diagnosed issue and a bounded fix unit.

### Unit 2: make the rig a required, trustworthy CI gate

Add an Xvfb/X11 backend to `hidden_session.py` with pinned Openbox and `xdotool` packages, then add
per-design CI selection, failure artifacts and timeouts. Prove that Escape and deactivation cancel
a gesture under the CI window manager. First make the rig's own failure paths trustworthy: a busy,
save or reload timeout must produce `FAIL` or `ERROR`, and every
persistence assertion must follow a confirmed fresh server load. Then implement cancel, scroll
dwell, rebuild-during-drag, rapid-second-move, non-centre hit, cross-view, restart, narrow-window and
large-text checks on Today's app. Trigger the rebuild case by advancing the frozen rig clock while
the pointer remains held. Add a deterministic helper that presses at 25%, 50% and 75% of a block's
visible length. Add arbitrary-week reads before Month scenarios join the matrix.

Done when:

- a missing surface, timeout, stale save or visible refusal mismatch fails the job;
- a scenario cannot pass by reading mutated in-memory state after a failed reload;
- a cross-week assertion reads fresh source and destination documents;
- reset removes history, selection, scroll and held state from the preceding scenario;
- the CI path cannot select the old drawer or canvas;
- the required set starts with Today's app Day and Week. A scenario joins the required set in the
  change that implements its feature, so Month joins in Unit 5 and each theme joins in its design
  unit. There are no expected failures inside the required set;
- Today's app passes three consecutive CI-equivalent runs;
- screenshots and a concise failure record are retained; and
- the job is separate from the 300-second source gate.

### Unit 3: finish the target, adapter and layout-hosting contracts

Define the small target protocol that `Hand` needs, route searches across all visible surfaces, and
give Day dial an explicit adapter proof. Add a Hand-backed adapter for draggable representations
that are not already `TrayChip`; do not switch the legacy `block_button` globally while unmigrated
layouts still use it. Give every layout access to the window-owned `Hand` and a default
`hours_surfaces()` contract. Centralize render hold, selection, judge and controller dispatch.
Layouts contribute tracks and painters only.

Done when:

- `Hand` can target a rectangular canvas and the dial adapter through one explicit contract;
- a minimal test layout can expose vertical, horizontal, rotated, partial-day and multiple canvases
  through the same public contract;
- the rig finds Monday through Sunday across several canvases and clicks the real visible day label
  for either time axis;
- track-local half-open bounds govern move, resize and create at partial-day boundaries;
- render hold starts on press, survives the threshold, queues only the latest scene and releases on
  tap, drop, Escape, deactivation or cancellation;
- a release over a gap or outside all hours emits the shared refusal and keeps the origin;
- a Month target calls the date-aware judge while held and can show a refused preview before release;
- tab, week, account and design changes cancel a held gesture without saving;
- a rebuild during a held gesture preserves the held identity and commits at most once; and
- an automated search finds no design-owned drag thresholds, snapping, judge, save logic or new
  `QDrag` use in the shared path.

### Unit 4: implement atomic cross-week MoveDate before Month

Define the occurrence payload and controller operation across two Monday-keyed week documents. Use
the existing multi-week changes transaction and fetch/write machinery, with Month-specific
completion that stays on the displayed month. Do this before a visible Month gesture depends on it.

Done when controller tests prove:

- same-week and cross-week moves preserve date-independent fields and local time;
- the occurrence payload contains the identity, source week, date, title, category, start, duration,
  assignment/series, pin and completion data needed to render and preserve a chip;
- a Sunday-to-Monday move and its reverse leave exactly one occurrence;
- the chosen recurring occurrence becomes one standalone block, the source series drops only that
  weekday, and every other occurrence keeps its date and time;
- one request contains both weeks and the client applies both returned revisions;
- a stale revision on either week or a validation failure rejects the whole transaction and leaves
  both documents unchanged;
- retry after a lost response reuses the same operation ID and cannot duplicate the destination;
- unrelated placements remain unchanged apart from expected document revision metadata;
- the displayed month stays selected, no destination-week navigation runs, and Month invalidates and
  refetches both affected weeks; and
- one history step captures both weeks. Undo runs the reverse atomic move, and the step becomes stale
  if either week reloads at a different revision before undo.

### Unit 5: build Month once with its complete contract

Add one shared `MonthCanvas` whose colours and painters may be supplied by a design. Do not build a
same-week-only intermediate UI. Every visible in-range cell follows the same rule.

Done when the full Month matrix passes in Today's app and proves:

- readable time-labelled chips, including more-than-four-chip overflow;
- date click to Day;
- same-week, adjacent-month-cell and cross-week moves with time preserved;
- a source-date drop sends no save and leaves the chip unchanged;
- occurrence-only movement;
- the held chip shows the shared after-due refusal before release and the source is restored; and
- save failure or conflict leaves the reloaded data and visible chip in the original date.

Today's app Month also exposes useful chip/date roles and names to the accessibility-tree test.

Each themed design unit later adds that design's Month painter and runs the same Month matrix. Unit
5 does not edit five layout files that Units 7 to 11 have not migrated yet.

### Unit 6: migrate My day before multiplying designs

Move One thing and Day dial to the shared hand without redesigning those screens. Their specialised
shapes should become tracks or selection/actions around the same controller operations.

Done when both screens:

- pass real-pointer move, tap/open, Escape, refusal and save/reload checks;
- use the Unit 3 target/adapter contract, shared judge and controller;
- contain no system drag-and-drop or private gesture policy; and
- expose literal accessible names and a keyboard path for the active item and its actions.

Units 7 to 11 share three gates. Each design passes the complete Day/Week matrix, adds its themed
Month painter and passes the Month matrix, and passes the accessibility-tree and keyboard-edit
checks from Unit 1. The unit-specific checks below add to those gates.

### Unit 7: Mission control Day and Week

Implement Scope lane and Lane ops if the owner accepts the recommendations. This is first because
horizontal time and compressed lanes test a different axis before other designs build on the
contract.

Done when the common matrix passes, both resize edges work horizontally, all seven lanes remain
readable and reachable at 1150x768 with large text, and a 15-minute block passes the three-point
grab test without a resize edge stealing the move. If that check fails under the recorded horizontal
zoom policy, apply the Column watch fallback before the unit is accepted.

### Unit 8: Clay deck Day and Week

Implement One big card and Fan hand. Cap visual tilt near 8 degrees and keep hit testing inside the
actual rotated track rather than the widget's bounding rectangle.

Done when the common matrix passes, blank space outside a rotated card is not a target, every visible
card remains reachable without overlap stealing its pointer, 15-minute blocks pass the three-point grab test,
and a supervised pointer check finds no precision-only grab. The current mock-up uses tilt up to 15
degrees, so rerun its drag check with the chosen near-8-degree values rather than citing the old pass
as evidence. Use Table hand if the recorded fallback condition is met.

### Unit 9: Retro desktop Day and Week

Implement Schedule.exe and Week.exe with the same engine. Window decoration and stacking may not
hide the hours or create a second input model.

Done when the common matrix passes, all seven days are visible or plainly reachable, focus and
z-order never redirect a gesture to another window, and the 1150x768 screenshots contain no clipped
buttons, dates or trays.

### Unit 10: Bento Day and Week

Implement Hero clock and Hero board. Keep the hero surface obvious enough that a first-time student
knows where to drag an unplaced item.

Done when the common matrix passes, all tray labels lead with plain words, the hero tile does not
hide fixed commitments or due feedback, and narrow/large-text screenshots keep every day and tray
reachable.

### Unit 11: Timeline Day and Week

Implement Column rule and Continuous scroll. Preserve the editorial look while keeping one clear
time direction and predictable edge scrolling.

Done when the common matrix passes, headings never become false drop targets, continuous scrolling
does not change the saved minute, unplaced homework in the margin has the plain tray label, and the
current day/date remain obvious after a cross-day move.

### Unit 12: delete the old gesture path

Remove the hours drawer, system `QDrag` helpers, legacy calendar canvas entry points and rig
fallbacks after their last consumers have moved. Delete compatibility adapters rather than keeping
two ways to perform the same action.

Done when:

- all six designs and both My day screens expose only the shared engine path;
- the targeted `rg` check has no unexplained old-path consumer;
- the full source and rig gates remain green; and
- a rerunnable mutation command deliberately breaks snap, due-date, occurrence and pin rules one at
  a time, and each change makes its named behaviour test fail.

### Unit 13: reconcile the contract and prepare release evidence

Update `architecture.md` to the code that shipped, including `hand.py`; update the dragging section
of `spec.md` only after explicit owner approval; then update the changelog and release notes. State
the X11, Wayland and Windows evidence accurately.

Done when the source gate, controller tests, full rig matrix, screenshot checklist, local videos and
supervised platform checks are complete; documentation contains no old drawer behaviour; and the
owner has explicitly requested the release/build step. Building executables and releasing 0.15 are
separate actions and occur only on that request.

## Risks and open questions

### Risk: cross-week movement can lose or duplicate work

This is the most serious engineering risk and was under-rated in the first plan. A Month grid does
not expose Monday-keyed storage, so refusing ordinary visible dates would feel arbitrary. A partial
two-document write is worse: it can duplicate or lose a student's commitment. Mitigation is Unit 4
before Month, one atomic controller contract, idempotent retry, conflict tests and no optimistic
completion before success.

**History answer:** one cross-week move creates one history step with before/after data for both
weeks. Undo runs the reverse atomic operation. If either week reloads at another revision before
undo, mark the whole step stale rather than restoring one side.

**Recommendation:** cross-week Month movement is required for 0.15. If it cannot be safe, defer all
Month chip dragging rather than ship a same-week-only rule.

### Risk: the rig can aim more precisely than a person

The current rig often presses `block_rect(...).center()`. Mission's compressed lanes and Clay's
rotated cards can pass while being frustrating with a mouse or touchpad. A fixed 24-pixel rule is
also impossible for a 15-minute block when Week fits all 17 hours. Mitigation is a 96-pixel-per-hour
minimum for scrollable Day, 25%, 50% and 75% grab points for whole-day Week, 1150x768 and large-text
evidence, and a short supervised feel check for the two risky designs.

**Recommendation:** keep Clay Fan hand only with tilt near 8 degrees and the target check. Use Table
hand if it fails. Use the same named fallback rule for Mission Lane ops.

### Risk: a rebuild interrupts a held gesture

Minute ticks, asynchronous saves and tab refreshes can rebuild the pressed surface. A rig that only
drags through a quiet screen will miss cancellation, duplication or offset errors. Mitigation is
one window-owned render hold, explicit cancellation on navigation and a scenario that triggers a
tick and unrelated save mid-drag.

### Risk: CI evidence is mistaken for platform evidence

Xvfb/X11 exercises the real pointer path but does not prove native Wayland or Windows focus,
scaling and input details. Mitigation is accurate CI wording plus supervised core checks on each
platform before release.

**Recommendation:** native-Wayland automation can wait. A supervised native-Wayland pass and a
Windows pass are release gates for 0.15.

### Risk: design scope multiplies before the contract is stable

Five Day/Week pairs can copy an early engine gap into ten surfaces. Mitigation is early CI,
risk-first Mission and Clay units, one design per review, and a rule that shared defects return to a
separate engine unit. A design must not add a private gesture branch to meet its visual concept.

**Recommendation:** do not split a design's Day and Week across releases. That would leave an
internally inconsistent design and weaken two fixed owner decisions.

### Risk: accessibility is implied but not delivered

Pointer parity does not provide full keyboard rescheduling. Adding it late would expand gesture,
focus and announcement scope across every surface. Painted blocks also do not automatically become
accessible Qt children. Mitigation for 0.15 is honest scope, keyboard focus and literal accessible
names, Enter to open, Escape to cancel, visible focus, announced refusal text, and a
keyboard-reachable form or parallel schedule list for editing day and time. An accessibility-tree
test checks role, name and open/edit action in every design.

**Recommendation:** add arrow-key movement and resizing in 0.15.1, with its own cross-design
acceptance matrix. Do not claim keyboard drag parity in 0.15.

### Risk: the gate becomes slow or flaky

The source gate is already near its 300-second budget and one combined selection stalled. A single
serial rig job for six designs would be slow and difficult to diagnose. Mitigation is a separate
per-design matrix, scenario timeouts, retained artifacts and a three-run reliability check after
engine changes. Raising the budget is not a substitute for finding a hang.

### Risk: invalid movement is silently clamped into a valid result

The current hand clamps candidate spans at the global planning bounds. That may make the fixed
outside-hours refusal impossible to reach: a student drops outside the day and sees an apparently
successful move at 06:00 or 23:00. It also ignores a partial track's own bounds. Mitigation is to
preserve the raw candidate long enough for the shared judge to refuse it, enforce track-local bounds
for partial surfaces, and add unit and real-pointer cases above, below and across a track boundary.
The original block must remain exact after reload.

### Risk: documentation describes a third behaviour

The architecture still names `session.py`, while `spec.md` describes old drawer behaviour for much
of the app. Mitigation is to treat the running contract and fixed decisions as the 0.15 target,
record drift now, and make the final doc reconciliation a release gate. The spec edit still requires
the owner's explicit approval.

### Open concept choices

Use the recommended concept table in this plan: Column rule/Continuous scroll, Scope lane/Lane ops,
Hero clock/Hero board, Schedule.exe/Week.exe, and One big card/Fan hand. The owner still makes the
selection before implementation. Mission and Clay carry explicit usability fallbacks; no other
concept remains open during a design unit.

## Changes from the first plan

- Moved the real-pointer CI gate before themed layout work so regressions cannot multiply silently.
- Moved atomic cross-week persistence before Month and rejected invisible same-week-only behaviour.
- Added a foundation unit for the missing target protocol, multiple-surface rig routing, dial and
  draggable adapters, track-local bounds, and render hold from press.
- Reordered design work by interaction risk: horizontal tracks, then rotated tracks, then the
  remaining visual layouts.
- Kept Day and Week together for every design and limited implementation to one selected concept.
- Added concrete unit completion rules, persisted predicates, target-size checks, failure cases and
  screenshot checkpoints.
- Added missing cancel, dwell, rebuild, overflow, adjacent-month, conflict, retry and narrow-window
  coverage at the test layer that can prove each behaviour.
- Required save/reload timeouts to fail and persistence checks to use a confirmed fresh server load,
  closing a false-green path in the current rig.
- Kept My day migration in 0.15 so the old drag system can be deleted instead of maintained beside
  the new one.
- Deferred arrow-key rescheduling and native-Wayland automation while keeping baseline keyboard and
  supervised platform checks.
- Made cross-week data safety and human target size the two leading risks.
