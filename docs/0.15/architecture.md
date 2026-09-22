# 0.15 hours engine: shape

## Problem

Every design gets hours to drag on, on Day and on Week, drawn its own way: columns down the page,
lanes across it, cards tilted in a fan, a day split into tiles, a desktop of windows. Homework with
no time is dragged in from a tray that is an ordinary widget somewhere else in the design, and a
Month chip is dragged from one date to another.

What exists today (grounding, traced in this session):

- `canvas.Timeline` is one painted widget with its own gesture code: press, move, resize from 7 px
  edges, create on empty time, Escape, the live preview through `laid_out()`, overlap columns. It
  only knows vertical columns. Today's app's week is built from it (`WeekCanvas`).
- Designs are `LayoutView`s that rebuild their widgets on every `render(scene)`, with `empty()`
  deleting the old ones. `show_week` holds a new scene back while `_dragging` is set, because a
  re-render mid-drag deletes the widget the drag started on.
- Everything that crosses widgets uses system drag-and-drop: `drag.start_drag` runs `QDrag.exec`,
  `Lift` and `Pickup` start it, `Zone` takes drops on painted axes (Mission's `Lanes`, the dial's
  `DialFace`, One thing's day bar), and `drawer.DropDrawer` slides a Timeline in for designs with no
  hours. `WaitingChip` starts its own `QDrag`. On Wayland this path is the platform's, and the rig
  showed the edge scroll firing on every move through an edge.
- The one rule is `NativeWindow._judge_span` (`span_problem`, `span_clash`, due point). Changes go
  through `_move_block` (with `_move_waiting` while a save is in flight), `_drop_block`,
  `place_session`, `move_occurrence` and `_create_range` (opens Add).
- Blocks belong to one week's document. Month shows other weeks from `month_data`, which the
  controller fetches; moving a block into another week is not an operation the controller has.

Constraints the shape must honour: one judge; renders held while a drag is on; the rig reaches every
surface through a small test interface (`reveal`, `point_for`, `block_rect`, `day_name`, and for
Month `cell_point`, `chip_point`, `chip_words`); no system drag-and-drop anywhere.

## Usage (caller's view)

A design builds its Day and Week from one widget per stretch of painted hours, and says where each
day's hours lie inside it.

```python
# Mission control's Week: seven lanes across, in one painted widget.
class MissionLanes(HoursCanvas):
    def lay_out(self, area: QRectF) -> list[Track]:
        lane = area.height() / 7
        return [LinearTrack(day, FROM, TO, QRectF(area.left() + 72, area.top() + day * lane,
                                                  area.width() - 72, lane), Axis.ACROSS)
                for day in range(7)]

lanes = MissionLanes(session, MissionPainter(tokens))
lanes.set_week(scene.week)            # occurrences to draw; nothing else to wire

# Clay deck's fan: one canvas per card, turned.
card = HoursCanvas(session, ClayPainter(tokens), tracks=lambda area: [
    LinearTrack(day, FROM, TO, area, Axis.DOWN, turn=angles[day])])

# A tray chip anywhere in a design: press and drag onto any hours.
tray = TrayChip(session, waiting)     # a QPushButton; a click still opens the homework
```

The window owns one session and applies what it reports:

```python
self.drags = DragSession(judge=self._judge_span, host=self)
self.drags.committed.connect(self._apply_change)      # Move, Place, Create or MoveDate
self.drags.refused.connect(self.session._say)
self.drags.active_changed.connect(self._hold_renders)  # no re-render while the pointer holds something
```

The rig asks a view for its surfaces and talks to them in global coordinates:

```python
hours = view.hours_surfaces()[0]
hours.reveal(3, 18 * 60, 21 * 60)
start = hours.block_rect(essay_id, 3).center()
end = hours.point_for(4, 18 * 60)
```

## Shape

Data first. Everything a gesture needs is five small immutable types:

```python
class Axis(Enum):
    DOWN = "down"       # minutes grow downward
    ACROSS = "across"   # minutes grow to the right

@dataclass(frozen=True)
class Span:
    day: int
    start: int
    end: int

class Track(Protocol):
    """One day's stretch of time inside a canvas: which day, which minutes, and where they are."""
    day: int
    first: int
    last: int
    def minute_at(self, point: QPointF) -> float: ...        # extrapolates outside; the session clamps
    def contains(self, point: QPointF) -> bool: ...
    def rect_for(self, start: int, end: int, column: int, columns: int) -> QPolygonF: ...
    def point_for(self, minute: int) -> QPointF: ...          # the middle of the track at that minute

@dataclass(frozen=True)
class LinearTrack:      # implements Track; `turn` rotates about the area's centre (Clay's fan)
    day: int; first: int; last: int; area: QRectF; axis: Axis; turn: float = 0.0

@dataclass(frozen=True)
class Held:
    """What the pointer holds, fixed at the press."""
    kind: Gesture       # MOVE, RESIZE_START, RESIZE_END, CREATE, PLACE, MOVE_DATE
    block_id: str | None
    title: str
    minutes: int
    from_day: int       # -1 for homework with no time
    origin: Span | None
    grab: int           # minutes between the block's start and the pointer

@dataclass(frozen=True)
class Preview:
    held: Held
    span: Span
    verdict: Verdict    # the window's judge, unchanged
```

`ArcTrack` (the dial) implements `Track` later with the same four methods; nothing else changes.

Three modules, each owning one decision:

- `hours/geometry.py` owns where minutes are: `Axis`, `Span`, `Track`, `LinearTrack`,
  `overlap_columns`, `snap`. Pure, no widgets, unit-tested with numbers.
- `hours/session.py` owns what the pointer is doing: `Held`, `Preview`, the `Change` union
  (`Move`, `Place`, `Create`, `MoveDate`) and `DragSession`. It is the deep module. Its public
  surface is `press(source, held, global_point)`, three signals, and `preview`. Behind it: the
  drag threshold, clicks versus drags, which canvas and track is under the pointer
  (`QApplication.widgetAt` then up the parents, so nothing registers and nothing leaks), snapping
  with the grab offset, clamping, resize rules, the judge call, the floating chip when over
  nothing, dwell auto-scroll (300 ms at a 36 px edge, then a steady step), Escape, a lost grab
  cancelling, and holding renders. Moves arrive through Qt's implicit grab: the widget pressed keeps
  receiving moves until release, on X11 and Wayland alike, and forwards them to the session.
- `hours/canvas.py` owns drawing hours and answering for them: `HoursCanvas(QWidget)` takes the
  week, lays out tracks through `lay_out(area)` (or a `tracks=` callable), paints rules, blocks,
  the held block and its label, the create ghost, the free-time hint and the now line through a
  `BlockPainter`, and provides the rig's test interface. `BlockPainter` is the one thing a design
  replaces to look like itself; a design never re-implements a gesture. `MonthCanvas` is the same
  idea for a month of dates.

`TrayChip(QPushButton)` is the one draggable widget outside a canvas; a design's cards that stand
for a block use `draggable(widget, session, held)` the same way.

Interface depth: a design writes `lay_out` and a painter, and gets every gesture, the judge, the
labels and the rig interface. The session hides the whole gesture policy behind one method; nothing
outside it knows the threshold, the snap, the edge width or the scroll dwell (per
boundary-discipline and model-the-domain: the gesture is a small state machine in one place).

What it deliberately does not do: no system drag-and-drop; no drag between weeks in the first
units (Month moves stay inside the loaded week, see open questions); no per-design gesture code.

## Synthesis decision

Two structurally different candidates were sketched.

- A. Each canvas runs its own gesture engine, as `Timeline` does now, and a window-level broker
  handles only drags that cross widgets (tray chips, Month, a design split across widgets). Close to
  the existing code, and in-canvas drags never leave the widget.
- B. One window-level session runs every gesture; canvases only lay out, paint and answer "what is
  here". Chips, blocks and Month chips all enter through `session.press`.

Base: B. A keeps two copies of the gesture policy (snap, grab offset, judge, labels, auto-scroll),
one inside canvases and one in the broker, which is the information leakage the red-flag screen
names, and the 0.14 bugs lived exactly in that split. Taken from A: a canvas owns several tracks in
one painted widget, so a week of seven columns or lanes is one widget with one paint pass, and
cross-track moves inside a canvas need no hit test across widgets. Rejected from A: per-canvas
gesture state.

Red-flag screen: `DragSession` is deep (one method in, three signals out). `HoursCanvas` is not a
pass-through; it owns layout, painting and hit-testing. No temporal split: judging, previewing and
committing share the `Held` and `Preview` types inside one module.

## Tradeoffs accepted

- We accept a canvas repainting on every session change in exchange for the held block being drawn
  in place, exactly where it will land.
- We accept one session per window (one pointer, one gesture) in exchange for no coordination
  between gestures.
- We accept that a design split across several widgets (Retro's seven windows, Clay's cards) uses
  several canvases in exchange for keeping each canvas a plain widget that stylesheets and layouts
  already understand.
- We accept `QApplication.widgetAt` per move in exchange for no registry to keep in step with
  renders.

## Alternatives considered

- A, per-canvas engines plus a broker. Lost on depth: the gesture policy is exposed twice.
- `QGraphicsView` scenes per design. Rotation and hit-testing come free, but every design's
  widget-and-stylesheet rendering would be rewritten as scene items, and chips outside the scene
  would still need a broker.
- Keep system drag-and-drop and fix the drawer. Lost because platform drag-and-drop is where
  Wayland and X11 differ and where the rig cannot see what the student sees.

## Open questions and risks

- Month drags across weeks. Blocks belong to one week's document. Should the first Month unit move
  blocks within the loaded week only, with other dates refused in words, and cross-week moves come
  after the controller can write two weeks in one save?
- Implicit grab after a re-render. The hold on renders must cover every path that rebuilds a
  design mid-drag, including the minute tick and a save finishing; the rig's scenarios with a save
  in flight watch this.
- Tilted tracks and hit-testing with `widgetAt`: a rotated card's widget rectangle is larger than
  the card. `Track.contains` decides, not the widget rectangle.

## Next implementation step

Write `hours/geometry.py` with `Span`, `LinearTrack` (both axes and `turn`) and `overlap_columns`,
with unit tests of `minute_at` and `rect_for` on literal numbers.
