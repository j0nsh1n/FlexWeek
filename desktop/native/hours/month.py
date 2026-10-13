"""Month, as Daily Scheduler draws it, and one thing more: a block can be carried to another date.

Daily Scheduler's month is one painted grid. Each date shows its day number and its events as chips
that start with their time; what does not fit becomes "and N more". A click selects the date and
fills the date pane; Open Day opens that day. FlexWeek draws the same, in weeks that start on Monday,
with the homework due that day as "Due" chips first. Overdue lives on the window's status strip, not
under the grid.

A chip with a time can also be carried: it is picked up by the one `Hand` as a date move, the hand
asks the window whether the block can go on the date under the pointer, and the date shows the
answer while the chip is held. Letting go reports a `MoveDate`; the window saves it. A deadline chip
is not carried: moving a deadline is editing the homework.

Today's app and every design show this grid through `MonthGrid`; a design dresses it with its
colour tokens.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from backend.models import due_is_timed
from desktop.native.calendar import DAYS
from desktop.native.fonts import caption, weighted
from desktop.native.hours.geometry import Span
from desktop.native.hours.hand import Gesture, Hand, Held, Verdict
from desktop.native.look import category_paint, luminance, resolved_palette
from desktop.native.tokens import WEIGHT_STRONG, mix, text_knob
from desktop.native.weekmodel import HOMEWORK as SESSION_CATEGORY
from desktop.native.weekmodel import WeekModel, clock_label, hhmm_text, length_label
from desktop.native.widgets import OverlayBar, Switch, overlay_scroll_bars

# The row of day names, kept above the dates while they scroll.
HEADER = 26
# The fewest chips a date always has room for; past them the month scrolls rather than squeezing.
LEAST_CHIPS = 2
# A week's row grows with its busiest date up to this many chips; the pane holds the rest.
MOST_CHIPS = 3
# While panels above it take the view, a row shrinks to its number and this many chips (#28).
TIGHT_CHIPS = 1
# This week's band: this much of the text colour over its dates, as the week washes today.
BAND = 0.04
# Layout passes to wait for the canvas's new height before scrolling to the first row.
REVEAL_TRIES = 3
# Date pane: rail-shaped card beside the grid, a drawer under this width (same as layouts.base).
PANE_PX = 300
PANE_NARROW = 1150
LOAD_CAP = 180
LOAD_WORDS = "Show study time per date"
CLOSE_PANE = "Close"
OPEN_DAY = "Open Day"
HOMEWORK = frozenset({"homework", "assignments"})


def more_label(count: int) -> str:
    return f"and {count} more"


@dataclass(frozen=True)
class MonthChip:
    """One line in a date: a block at its time, or homework due that day."""

    key: str
    title: str
    category: str
    block_id: str | None = None
    start: int | None = None
    minutes: int = 0
    due: bool = False
    due_time: str | None = None
    done: bool = False
    # Due on a date already gone and not finished.
    late: bool = False
    history: str = ""

    @property
    def carried(self) -> bool:
        """A block with a time can be carried to another date. A deadline cannot."""
        return self.block_id is not None and self.start is not None and not self.due

    @property
    def flag(self) -> str:
        """The state word shown before a deadline or a carried block."""
        if self.history:
            return self.history
        if not self.due:
            return ""
        if self.late:
            return "Overdue"
        return f"Due {hhmm_text(self.due_time)}" if self.due_time else "Due"

    @property
    def words(self) -> str:
        if self.due or self.history:
            if self.history and not self.due:
                return f"{self.flag} {clock_label(self.start or 0)} {self.title}"
            return f"{self.flag} {self.title}"
        return f"{clock_label(self.start or 0)} {self.title}"


@dataclass(frozen=True)
class MonthCell:
    iso: str
    in_month: bool
    today: bool
    chips: tuple[MonthChip, ...]
    planned_min: int = 0
    completed_min: int = 0

    @property
    def day_number(self) -> int:
        return int(self.iso[8:])


def month_cells(snapshot: dict | None, weeks: Mapping[str, WeekModel], today_iso: str) -> list[MonthCell]:
    """The dates of a month reply, each with its chips. `weeks` are the weeks the student has now,
    saved or not, by their Monday: a date in one of them is read from it; any other date from what
    the reply says is on it."""
    if not snapshot:
        return []
    deadlines: dict[str, dict] = {}
    for item in list(snapshot.get("deadlines") or []) + list(snapshot.get("overdue") or []):
        if item.get("id"):
            deadlines[str(item["id"])] = item
    open_days: dict[str, tuple] = {}
    for week_start, week in weeks.items():
        monday = date.fromisoformat(week_start)
        for offset in range(7):
            day_iso = (monday + timedelta(days=offset)).isoformat()
            open_days[day_iso] = tuple(item for item in week.occurrences if item.day == offset)
    cells = []
    for day in snapshot.get("days") or []:
        iso = str(day["date"])
        chips: list[MonthChip] = []
        for aid in day.get("due_ids") or []:
            item = deadlines.get(str(aid), {"id": aid, "title": aid})
            due = str(item.get("due") or "")
            chips.append(
                MonthChip(
                    f"due:{aid}",
                    str(item.get("title") or aid),
                    str(item.get("category") or "assignments"),
                    due=True,
                    due_time=due[11:16] if due and due_is_timed(due) else None,
                    done=bool(item.get("completed")),
                    late=iso < today_iso and not item.get("completed"),
                )
            )
        blocks: list[MonthChip] = []
        if iso in open_days:
            for item in open_days[iso]:
                blocks.append(
                    MonthChip(
                        f"block:{item.block_id}",
                        item.title,
                        item.category,
                        block_id=item.block_id,
                        start=item.start,
                        minutes=item.end - item.start,
                        done=item.done,
                        history=item.history,
                    )
                )
        else:
            for item in day.get("blocks") or []:
                start = str(item.get("start") or "")
                if len(start) != 5:
                    continue
                blocks.append(
                    MonthChip(
                        f"block:{item['id']}",
                        str(item.get("title") or "Untitled"),
                        # A homework session is saved with no category unless the student picked one.
                        str(item.get("category") or (SESSION_CATEGORY if item.get("assignment_id") else "")),
                        block_id=str(item["id"]),
                        start=int(start[:2]) * 60 + int(start[3:]),
                        minutes=int(item.get("duration_min") or 0),
                        done=bool(item.get("completed")),
                        history=str(item.get("history") or ""),
                    )
                )
        blocks.sort(key=lambda chip: (chip.start or 0, chip.title))
        sessions = [block for block in blocks if block.category in HOMEWORK]
        planned = sum(block.minutes for block in sessions)
        completed = sum(block.minutes for block in sessions if block.done)
        cells.append(
            MonthCell(
                iso,
                bool(day.get("in_month")),
                iso == today_iso,
                tuple(chips + blocks),
                planned,
                completed,
            )
        )
    return cells


class MonthPainter:
    """How the month looks. A design gives its own colours; the shapes are Daily Scheduler's."""

    def __init__(self, colours: dict[str, str]) -> None:
        self.colours = {
            "window": "#ffffff",
            "text": "#0f172a",
            "muted": "#64748b",
            "panel": "#ffffff",
            "hairline": "#e2e8f0",
            "accent": "#2563eb",
            "accent_ink": "#ffffff",
            "error": "#dc2626",
            **{key: value for key, value in colours.items() if isinstance(value, str)},
        }

    def c(self, name: str) -> QColor:
        return QColor(self.colours[name])

    def cell(self, painter: QPainter, box: QRectF, cell: MonthCell, band: bool = False) -> None:
        # A date outside the month is told by its dimmed number, not a tint: tinted, it looked like today.
        # This week is banded in a little of the text colour, never the accent.
        painter.fillRect(box, self.c("panel"))
        if band:
            wash = self.c("text")
            wash.setAlphaF(BAND)
            painter.fillRect(box, wash)
        painter.setPen(QPen(self.c("hairline"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(box)

    def day_number(self, painter: QPainter, box: QRectF, cell: MonthCell) -> None:
        side = max(22.0, QFontMetrics(painter.font()).height() + 4)
        spot = QRectF(box.left() + 5, box.top() + 3, side, side)
        if cell.today:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.c("accent"))
            painter.drawEllipse(spot)
            painter.setPen(self.c("accent_ink"))
        else:
            painter.setPen(self.c("text") if cell.in_month else self.c("muted"))
        painter.drawText(spot, Qt.AlignmentFlag.AlignCenter, str(cell.day_number))

    def load_bar(self, painter: QPainter, box: QRectF, cell: MonthCell, under: float) -> None:
        if cell.planned_min <= 0 and cell.completed_min <= 0:
            return
        track = QRectF(box.left() + 5, box.top() + under - 5, max(box.width() - 10, 1), 3)
        tint = QColor(mix(self.colours["accent"], self.colours["panel"], 0.35))
        planned = min(cell.planned_min / LOAD_CAP, 1.0) * track.width()
        done = min(cell.completed_min / LOAD_CAP, 1.0) * track.width()
        painter.fillRect(QRectF(track.left(), track.top(), planned, track.height()), tint)
        painter.fillRect(QRectF(track.left(), track.top(), done, track.height()), self.c("accent"))

    def chip(self, painter: QPainter, box: QRectF, chip: MonthChip, faded: bool, held: bool) -> None:
        """A block in its category's fill, as the week draws it, or a deadline as a quiet chip led by
        a bold "Due". A column of red boxes was the most alarming thing in the app for its most
        ordinary fact; the flag is red only once the date has gone."""
        category_fill = None if chip.due else category_paint(chip.category, self.colours)[0]
        if category_fill is None:
            fill = self.c("text")
            fill.setAlpha(18)
        else:
            fill = QColor(category_fill)
        ink = self.c("text")
        flag = self.c("text")
        if faded or chip.done or held:
            # Only the fill says "done"; dimmed words were too faint to read (#93).
            fill.setAlpha(fill.alpha() // 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(box, 4, 4)
        room = box.adjusted(5, 0, -3, 0)
        wrap = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap
        words = chip.words
        if chip.due or chip.history:
            plain = painter.font()
            bold = weighted(plain, WEIGHT_STRONG)
            painter.setFont(bold)
            painter.setPen(flag)
            painter.drawText(room, wrap, chip.flag)
            room.setLeft(room.left() + QFontMetrics(bold).horizontalAdvance(chip.flag + " "))
            painter.setFont(plain)
            words = chip.title if chip.due else f"{clock_label(chip.start or 0)} {chip.title}"
        painter.setPen(ink)
        if room.width() > 0:
            painter.drawText(room, wrap, words)

    def more(self, painter: QPainter, box: QRectF, count: int) -> None:
        painter.setPen(self.c("muted"))
        painter.drawText(box.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, more_label(count))

    def target(self, painter: QPainter, box: QRectF, verdict: Verdict | None) -> None:
        refused = verdict is not None and not verdict.ok
        painter.setPen(QPen(self.c("error" if refused else "accent"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(box.adjusted(1, 1, -1, -1))

    def header(self, painter: QPainter, box: QRectF, words: str) -> None:
        painter.setPen(self.c("muted"))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, words)


class MonthCanvas(QWidget):
    """The month's dates, painted. A surface the hand carries dates onto (see hand.py)."""

    takes_dates = True
    date_opened = Signal(str)
    # Arrow keys move the selected date; Enter or Space opens it.
    date_moved = Signal(str)
    date_entered = Signal(str)

    def __init__(self, hand: Hand, painter: MonthPainter, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monthCanvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Month")
        self.hand, self.painter = hand, painter
        self.cells: list[MonthCell] = []
        # The Monday of the week the window has open: only its blocks have a menu, since the same id
        # can stand for a block on another week, such as School.
        self.open_week: str | None = None
        self._pressed: str | None = None
        # The row the month opened on, the height of the view it scrolls in, and each row's height.
        self._lead = 0
        self._room = 0
        self._heights: list[float] = []
        # Set while the plan or Unfinished panel is open: the rows then shrink to fit rather than scroll.
        self._tight = False
        self.selected: str | None = None
        self._show_load = False
        self._bar_inset = 0
        hand.preview_changed.connect(self.update)

    def set_cells(self, cells: list[MonthCell]) -> None:
        if not cells or not self.cells or cells[0].iso != self.cells[0].iso:
            self._lead = 0
        self.cells = cells
        self._fit()
        self.setAccessibleDescription(
            "Click a date to see it. Open Day opens that day. "
            "Drag a block with a time to another date to move it there."
        )
        self.update()

    def set_painter(self, painter: MonthPainter) -> None:
        self.painter = painter
        self.update()

    def set_room(self, room: int) -> None:
        """The height the month scrolls in."""
        if room != self._room:
            self._room = room
            self._fit()

    def set_tight(self, tight: bool) -> None:
        if tight != self._tight:
            self._tight = tight
            self._fit()

    def set_show_load(self, on: bool) -> None:
        self._show_load = on
        self.update()

    def lead_with(self, row: int) -> None:
        """Open on this row: the weeks from it to the month's end fill the view."""
        self._lead = max(0, min(row, self.rows() - 1))
        self._fit()

    def _fit(self) -> None:
        """Each week's row as tall as its busiest date's chips, from two to three. Room over is shared
        from the first row, so the month opens with that row fully visible."""
        heights = [self.base_row(row) for row in range(self.rows())]
        if self._tight and sum(heights) > self._room:
            squeezed = self._squeezed(heights)
            if squeezed is not None:
                self._heights = squeezed
                self.setMinimumHeight(math.ceil(sum(squeezed)))
                self.update()
                return
        start = 0
        spare = self._room - sum(heights[start:])
        if spare > 0 and heights:
            share = spare / (len(heights) - start)
            heights = [height + (share if at >= start else 0) for at, height in enumerate(heights)]
        self._heights = heights
        self.setMinimumHeight(math.ceil(sum(heights)))
        self.update()

    def _squeezed(self, heights: list[float]) -> list[float] | None:
        """Every row between its tight size and its own, so together they are exactly the view; None when
        even the tight rows do not fit, and the month scrolls as it does with nothing open."""
        low = self.tight_row()
        if self._room < low * len(heights):
            return None
        share = (self._room - low * len(heights)) / sum(height - low for height in heights)
        return [math.floor(low + (height - low) * share) for height in heights]

    def base_row(self, row: int) -> float:
        """A week's row at its own size: its busiest date's chips, from LEAST_CHIPS to MOST_CHIPS,
        and a line for "and N more"."""
        busiest = max((len(cell.chips) for cell in self.cells[row * 7 : row * 7 + 7]), default=0)
        chips = min(max(busiest, LEAST_CHIPS), MOST_CHIPS)
        return round(self.number_height() + chips * self.pitch() + self.pitch() + 4)

    def _row_tops(self) -> list[float]:
        """Where each row starts, with any height the view adds shared by every row."""
        heights = self._heights if len(self._heights) == self.rows() else [self.least_row()] * self.rows()
        extra = max(self.height() - sum(heights), 0) / max(len(heights), 1)
        tops, at = [], 0.0
        for height in heights:
            tops.append(at)
            at += height + extra
        tops.append(at)
        return tops

    # Where things are

    def rows(self) -> int:
        return max(1, (len(self.cells) + 6) // 7)

    def _small(self) -> QFont:
        return caption(self.font())

    def _chip_lines(self) -> int:
        return 2 if text_knob(self.font().pointSizeF()) == "large" else 1

    def chip_height(self) -> float:
        return QFontMetrics(self._small()).height() * self._chip_lines() + 2

    def pitch(self) -> float:
        return self.chip_height() + 3

    def number_height(self) -> float:
        return max(27.0, QFontMetrics(self.font()).height() + 11)

    def tight_row(self) -> int:
        # Exactly what _slots needs for TIGHT_CHIPS lines. Two pixels more of padding left a 1024x640
        # window 4 px short of fitting Month with the Unfinished panel open (#28).
        return math.ceil(self.number_height() + 2 + TIGHT_CHIPS * self.pitch())

    def least_row(self) -> int:
        return round(self.number_height() + LEAST_CHIPS * self.pitch() + self.pitch() + 4)

    def cell_rect(self, index: int) -> QRectF:
        row, column = divmod(index, 7)
        wide = max(self.width() - self._bar_inset, 1) / 7
        tops = self._row_tops()
        return QRectF(column * wide, tops[row], wide, tops[row + 1] - tops[row])

    def index_of(self, iso: str) -> int | None:
        return next((at for at, cell in enumerate(self.cells) if cell.iso == iso), None)

    def date_at(self, point: QPointF) -> str | None:
        if not self.cells:
            return None
        for at, cell in enumerate(self.cells):
            if self.cell_rect(at).contains(point):
                return cell.iso
        return None

    def chip_boxes(self, index: int) -> tuple[list[tuple[MonthChip, QRectF]], int]:
        """The chips a date shows, each with its box, and how many more did not fit."""
        box = self.cell_rect(index)
        chips = self.cells[index].chips
        room = self._slots(index)
        fits = min(room, MOST_CHIPS)
        if len(chips) > fits and fits != 1 and fits == room:
            fits = max(0, fits - 1)
        shown = [
            (
                chip,
                QRectF(
                    box.left() + 4,
                    box.top() + self.number_height() + at * self.pitch(),
                    box.width() - 8,
                    self.chip_height(),
                ),
            )
            for at, chip in enumerate(chips[:fits])
        ]
        return shown, len(chips) - len(shown)

    def _slots(self, index: int) -> int:
        """How many chip lines a date has room for."""
        room = self.cell_rect(index).height() - self.number_height() - 2
        return max(0, int(room // self.pitch()))

    def _more_beside_number(self, index: int) -> bool:
        """With room for one chip line, the chip keeps it and "and N more" goes by the date's number."""
        return self._slots(index) == 1

    def more_box(self, index: int, shown: int) -> QRectF:
        """Where "and N more" is written: under the chips, or by the number when there is one line."""
        box = self.cell_rect(index)
        if self._more_beside_number(index):
            side = max(22.0, QFontMetrics(self.font()).height() + 4)
            left = box.left() + 5 + side
            return QRectF(left, box.top() + 3, box.right() - left - 3, side)
        return QRectF(
            box.left(),
            box.top() + self.number_height() + shown * self.pitch(),
            box.width(),
            self.chip_height(),
        )

    def _chip_at(self, point: QPointF) -> tuple[MonthCell, MonthChip, QRectF] | None:
        for at, cell in enumerate(self.cells):
            if not self.cell_rect(at).contains(point):
                continue
            for chip, box in self.chip_boxes(at)[0]:
                if box.contains(point):
                    return cell, chip, box
            return None
        return None

    # Painting

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.painter.c("window"))
        held = self.hand.preview_held()
        target = self.hand.month_target if held is not None else None
        bands = {at // 7 for at, cell in enumerate(self.cells) if cell.today}
        for at, cell in enumerate(self.cells):
            box = self.cell_rect(at)
            self.painter.cell(painter, box, cell, at // 7 in bands)
            painter.setFont(self.font())
            self.painter.day_number(painter, box, cell)
            if self._show_load:
                self.painter.load_bar(painter, box, cell, self.number_height())
            painter.setFont(self._small())
            shown, more = self.chip_boxes(at)
            for chip, chip_box in shown:
                lifted = held is not None and chip.block_id == held.block_id and cell.iso == held.from_iso
                self.painter.chip(painter, chip_box, chip, not cell.in_month, lifted)
            if more:
                self.painter.more(painter, self.more_box(at, len(shown)), more)
            if target == cell.iso:
                self.painter.target(painter, box, self.hand.month_verdict)
            elif cell.iso == self.selected:
                self.painter.target(painter, box, Verdict(True, ""))
        painter.end()

    # Pointer

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        point = event.position()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        found = self._chip_at(point)
        if found is not None and found[1].carried:
            cell, chip, _box = found
            weekday = date.fromisoformat(cell.iso).weekday()
            start = chip.start or 0
            held = Held(
                Gesture.MOVE_DATE,
                chip.title,
                chip.minutes,
                chip.block_id,
                weekday,
                Span(weekday, start, start + chip.minutes),
                0,
                cell.iso,
            )
            # A chip that is only clicked opens its date, as a click anywhere on a date does.
            self.hand.press(
                self, held, event.globalPosition().toPoint(), tap=lambda: self.date_opened.emit(cell.iso)
            )
            return
        self._pressed = self.date_at(point)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        steps = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1, Qt.Key.Key_Up: -7, Qt.Key.Key_Down: 7}
        at = self.index_of(self.selected) if self.selected else None
        key = event.key()
        if key in steps and self.cells and not event.modifiers():
            target = 0 if at is None else min(max(at + steps[key], 0), len(self.cells) - 1)
            self.date_moved.emit(self.cells[target].iso)
            event.accept()
            return
        opens = key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
        if opens and self.selected and at is not None:
            self.date_entered.emit(self.selected)
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """A right-click on a block of the open week asks for its menu. A deadline has none."""
        found = self._chip_at(QPointF(event.pos()))
        if found is None or found[1].block_id is None or found[1].due or self.hand.busy:
            event.ignore()
            return
        cell, chip, _box = found
        day = date.fromisoformat(cell.iso)
        if (day - timedelta(days=day.weekday())).isoformat() != self.open_week:
            event.ignore()
            return
        event.accept()
        self.hand.ask_menu(chip.block_id, day.weekday(), event.globalPos())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pressed, self._pressed = self._pressed, None
        if (
            event.button() == Qt.MouseButton.LeftButton
            and pressed
            and pressed == self.date_at(event.position())
        ):
            self.date_opened.emit(pressed)
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.hand.busy:
            return
        found = self._chip_at(event.position())
        carried = found is not None and found[1].carried
        self.setCursor(Qt.CursorShape.OpenHandCursor if carried else Qt.CursorShape.PointingHandCursor)

    # For the rig and the tests, in global coordinates

    def chip_words(self, block_id: str, iso: str) -> str:
        at = self.index_of(iso)
        chip = (
            next((chip for chip in self.cells[at].chips if chip.block_id == block_id), None)
            if at is not None
            else None
        )
        if chip is None:
            raise LookupError(f"no chip for {block_id} on {iso}")
        return chip.words

    def chip_point(self, block_id: str, iso: str) -> QPoint:
        at = self.index_of(iso)
        if at is not None:
            for chip, box in self.chip_boxes(at)[0]:
                if chip.block_id == block_id:
                    return self.mapToGlobal(box.center().toPoint())
        raise LookupError(f"{block_id} is not drawn on {iso}")

    def cell_point(self, iso: str) -> QPoint:
        """A point on the date that is on none of its chips: the middle of the room under them."""
        at = self.index_of(iso)
        if at is None:
            raise LookupError(f"{iso} is not in this month")
        box = self.cell_rect(at)
        shown, more = self.chip_boxes(at)
        below = 1 if more and not self._more_beside_number(at) else 0
        used = self.number_height() + (len(shown) + below) * self.pitch()
        free = (used + box.height()) / 2 if used < box.height() - 6 else box.height() - 3
        return self.mapToGlobal(QPointF(box.center().x(), box.top() + free).toPoint())

    def reveal(self, iso: str) -> None:
        """Scroll the nearest scroll area so this date is wholly on screen, clear of its edges."""
        at = self.index_of(iso)
        area = self.parentWidget()
        while area is not None and not isinstance(area, QScrollArea):
            area = area.parentWidget()
        if at is None or area is None:
            return
        box = self.cell_rect(at)
        area.ensureVisible(round(box.center().x()), round(box.center().y()), 0, round(box.height() / 2) + 40)


class MonthNames(QWidget):
    """Monday to Sunday over the dates, in the canvas's own colours, kept in place as they scroll."""

    def __init__(self, canvas: MonthCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monthNames")
        self.canvas = canvas

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.canvas.painter.c("window"))
        font = weighted(self.canvas._small(), WEIGHT_STRONG)
        painter.setFont(font)
        wide = max(self.width() - self.canvas._bar_inset, 1) / 7
        for column in range(7):
            self.canvas.painter.header(painter, QRectF(column * wide, 0, wide, self.height()), DAYS[column])
        painter.end()


class MonthScroll(QScrollArea):
    """The dates scroll; the names above them do not, and are always exactly as wide as the dates."""

    def __init__(self, canvas: MonthCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monthScroll")
        overlay_scroll_bars(self)
        self.names = MonthNames(canvas, self)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(canvas)
        self.setViewportMargins(0, HEADER, 0, 0)
        self.verticalScrollBar().rangeChanged.connect(self._gutter)

    def _gutter(self, *_: object) -> None:
        extra = OverlayBar.WIDE + OverlayBar.EDGE if self.verticalScrollBar().maximum() > 0 else 0
        canvas = self.widget()
        if isinstance(canvas, MonthCanvas) and canvas._bar_inset != extra:
            canvas._bar_inset = extra
            canvas.update()
        self._place()

    def _place(self) -> None:
        port = self.viewport().geometry()
        self.names.setGeometry(port.left(), port.top() - HEADER, port.width(), HEADER)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._gutter()

    def viewportEvent(self, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Resize:
            self._gutter()
            canvas = self.widget()
            if isinstance(canvas, MonthCanvas):
                canvas.set_room(self.viewport().height())
        return super().viewportEvent(event)


class DatePane(QFrame):
    """The selected date: due work first, then blocks, a load switch, and Open Day."""

    open_day = Signal()
    load_toggled = Signal(bool)
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monthDatePane")
        self.setFixedWidth(PANE_PX)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName("monthPaneHeading")
        self.heading.setWordWrap(True)
        top.addWidget(self.heading, 1)
        # Only a drawer closes; beside the grid the pane is always there.
        self.close_button = QPushButton(CLOSE_PANE)
        self.close_button.setObjectName("monthPaneClose")
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.hide()
        top.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        self.load_switch = Switch(LOAD_WORDS)
        self.load_switch.setObjectName("monthLoadSwitch")
        self.load_switch.toggled.connect(self.load_toggled.emit)
        layout.addWidget(self.load_switch)
        self.rows = QVBoxLayout()
        layout.addLayout(self.rows)
        layout.addStretch(1)
        self.summary = QLabel()
        self.summary.setObjectName("monthPaneSummary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.open = QPushButton(OPEN_DAY)
        self.open.setObjectName("monthOpenDay")
        self.open.clicked.connect(self.open_day.emit)
        layout.addWidget(self.open)

    def set_drawer(self, drawer: bool) -> None:
        self.close_button.setVisible(drawer)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self.close_button.isVisible():
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def fill(self, cell: MonthCell | None) -> None:
        if not isValid(self):
            return
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if cell is None:
            self.heading.setText("")
            self.summary.setText("")
            return
        day = date.fromisoformat(cell.iso)
        self.heading.setText(f"{day.strftime('%A')} {day.day} {day.strftime('%B')}")
        for chip in cell.chips:
            line = QLabel(_pane_line(chip))
            line.setWordWrap(True)
            self.rows.addWidget(line)
        planned = length_label(cell.planned_min) if cell.planned_min else "0"
        done = length_label(cell.completed_min) if cell.completed_min else "0"
        self.summary.setText(f"{planned} homework planned · {done} completed")


def _pane_line(chip: MonthChip) -> str:
    if chip.due or chip.history:
        return chip.words
    when = clock_label(chip.start or 0)
    length = f" · {length_label(chip.minutes)}" if chip.minutes else ""
    mark = "✓ " if chip.category in HOMEWORK and chip.done else ""
    return f"{mark}{when} {chip.title}{length}"


class MonthGrid(QWidget):
    """A month: a note while changes are still saving, the dates, and the date pane. The window's
    heading already names the month, so the grid does not say it again. Overdue lives on the strip."""

    day_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None, *, hand: Hand | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("monthPageInner")
        layout = QVBoxLayout(self)
        self.warning = QLabel()
        self.warning.setObjectName("monthSavedWarning")
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        # A month drawn with no window takes nothing and moves nothing; its hand belongs to it.
        self.hand = (
            hand if hand is not None else Hand(lambda block_id, from_day, span: Verdict(False, ""), self)
        )
        self._palette = resolved_palette("system", False, None)
        self.canvas = MonthCanvas(self.hand, MonthPainter(self._palette))
        self.canvas.date_opened.connect(self._date_chosen)
        self.canvas.date_moved.connect(self._date_moved)
        self.canvas.date_entered.connect(self._date_entered)
        self.scroll = MonthScroll(self.canvas)
        self.body = QWidget()
        split = QHBoxLayout(self.body)
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(8)
        split.addWidget(self.scroll, 1)
        self.pane = DatePane()
        self.pane.open_day.connect(self._open_day)
        self.pane.load_toggled.connect(self.canvas.set_show_load)
        self.pane.close_requested.connect(self.close_drawer)
        # Under PANE_NARROW the pane is a drawer over the grid, closed until a date is chosen.
        self._drawer_open = False
        split.addWidget(self.pane)
        self._split = split
        layout.addWidget(self.body, 1)
        self.overdue = QLabel()
        self.overdue.setObjectName("monthOverdue")
        self.overdue.hide()
        self._week: WeekModel | None = None
        self._unsaved: Mapping[str, WeekModel] = {}
        self._shown: tuple[dict | None, bool, str | None, str | None] | None = None
        # Whose month is drawn, so a month on its way never shows another student's grid.
        self._drawn_for: str | None = None

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)
        self._place_pane()

    def set_tight(self, tight: bool) -> None:
        """Panels above the month are open: its rows shrink to fit the view rather than scroll."""
        self.canvas.set_tight(tight)

    def set_palette(self, palette: dict) -> None:
        self._palette = palette
        self.canvas.set_painter(MonthPainter(palette))
        self.scroll.names.update()

    def set_tokens(self, tokens: dict[str, str]) -> None:
        """A layout's own colours, so Month is not the pack's calendar sitting inside Bento."""
        self.setStyleSheet(
            f"#monthPageInner, #monthScroll {{ background: {tokens['bg']}; color: {tokens['bg_ink']}; }}"
            f"#monthOverdue, #monthSavedWarning {{ color: {tokens['bg_muted']}; }}"
        )
        self.canvas.set_painter(
            MonthPainter(
                {
                    "window": tokens["bg"],
                    "text": tokens["bg_ink"],
                    "muted": tokens["bg_muted"],
                    "panel": tokens["surface"],
                    "hairline": tokens["line"],
                    "accent": tokens["accent"],
                    "accent_ink": tokens.get("accent_ink", "#ffffff"),
                    # A dark design's cells take its categories sunk into them, as a dark look's do.
                    "family": "dark" if luminance(tokens["surface"]) < 0.2 else "light",
                }
            )
        )
        self.scroll.names.update()

    def set_week(self, week: WeekModel | None) -> None:
        """The open week as the student has it now, saved or not."""
        self._week = week
        if self._shown is not None:
            self.set_month(*self._shown)

    def set_unsaved(self, weeks: Mapping[str, WeekModel]) -> None:
        """Weeks the student changed and left without saving, by their Monday, as they have them."""
        self._unsaved = weeks
        if self._shown is not None:
            self.set_month(*self._shown)

    def set_month(
        self, snapshot: dict | None, dirty: bool, today_iso: str | None = None, account: str | None = None
    ) -> None:
        """`snapshot` is None while a month is on its way. The grid then stays as the same `account`
        last had it, under "Loading month…", rather than flashing empty."""
        self._shown = (snapshot, dirty, today_iso, account)
        if snapshot is None:
            if account is None or account != self._drawn_for:
                self.canvas.set_cells([])
            self._say(self.warning, "Loading month…")
            return
        self._drawn_for = account
        # Every week is drawn as the student has it, saved or not, so there is no "saved only" to say.
        self._say(self.warning, "")
        weeks = dict(self._unsaved)
        if self._week is not None and self._week.week_start:
            weeks[self._week.week_start] = self._week
        self.canvas.open_week = self._week.week_start if self._week is not None else None
        today = today_iso or date.today().isoformat()
        self.canvas.set_cells(month_cells(snapshot, weeks, today))
        self._say(self.overdue, "")
        chosen = self.canvas.selected
        if chosen is None or self.canvas.index_of(chosen) is None:
            chosen = today if self.canvas.index_of(today) is not None else next(
                (cell.iso for cell in self.canvas.cells if cell.in_month), None
            )
        if chosen:
            self.select(chosen)

    @staticmethod
    def _say(label: QLabel, words: str) -> None:
        # An empty line takes no room: the dates have it.
        label.setText(words)
        label.setVisible(bool(words))

    def select(self, iso: str) -> None:
        if not isValid(self):
            return
        self.canvas.selected = iso
        cell = next((item for item in self.canvas.cells if item.iso == iso), None)
        self.pane.fill(cell)
        self.canvas.update()

    def drawer(self) -> bool:
        return self.width() < PANE_NARROW

    def _date_chosen(self, iso: str) -> None:
        self.select(iso)
        if self.drawer():
            self._drawer_open = True
            self._place_pane()

    def _date_moved(self, iso: str) -> None:
        self.select(iso)
        self.canvas.reveal(iso)

    def _date_entered(self, iso: str) -> None:
        if self.drawer() and not self._drawer_open:
            self._date_chosen(iso)
            self.pane.open.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.select(iso)
            self._open_day()

    def close_drawer(self) -> None:
        if not self._drawer_open:
            return
        self._drawer_open = False
        self._place_pane()
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_day(self) -> None:
        if self.canvas.selected:
            self.day_activated.emit(self.canvas.selected)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_pane()

    def _place_pane(self) -> None:
        drawer = self.drawer()
        self.pane.setFixedWidth(PANE_PX)
        self.pane.set_drawer(drawer)
        if drawer:
            if self._split.indexOf(self.pane) >= 0:
                self._split.removeWidget(self.pane)
                self.pane.setParent(self)
            top = 0 if self.warning.isHidden() else self.warning.sizeHint().height()
            self.pane.setGeometry(max(0, self.width() - PANE_PX), top, PANE_PX, max(0, self.height() - top))
            # Closed, all seven days are on screen; open, it covers the right of the grid until closed.
            self.pane.setVisible(self._drawer_open)
            if self._drawer_open:
                self.pane.raise_()
        else:
            self._drawer_open = False
            if self._split.indexOf(self.pane) < 0:
                self._split.addWidget(self.pane)
            self.pane.show()

    def reveal(self, iso_day: str) -> None:
        """Open the month with its first row fully visible; this week stays banded."""
        if not isValid(self):
            return
        if self.canvas.index_of(iso_day) is not None:
            self.select(iso_day)
            self._scroll_to(0, REVEAL_TRIES)

    def _scroll_to(self, row: int, tries: int) -> None:
        canvas = self.canvas
        if not self.scroll.viewport().isVisible() and tries > 0:
            # A month just switched to has no height of its own until its first layout pass.
            QTimer.singleShot(0, self, lambda: self._scroll_to(row, tries - 1))
            return
        canvas.set_room(self.scroll.viewport().height())
        canvas.lead_with(0)
        self.scroll.verticalScrollBar().setValue(0)
        self.scroll._gutter()

    def month_surfaces(self) -> list[MonthCanvas]:
        return [self.canvas] if self.canvas.isVisible() else []
