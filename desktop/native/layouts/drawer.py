"""A day's hours, slid in beside a design while a block is dragged, so every drop is at a time.

Bento, Timeline, Retro desktop and Clay deck show days as tiles, cards, columns and lists, none of which
has an hour to let a block go on. While a block is dragged in one of them, this drawer opens on the
right with the day as Today's app's timeline draws it. Holding the pointer over another day's name
turns the drawer to that day. Let go on the hours and the block goes there, at that time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout

from backend.slots import DAY_START_MIN
from desktop.native.calendar import DAY_FULL, DAYS
from desktop.native.canvas import Shape, Timeline
from desktop.native.layouts.drag import carried
from desktop.native.motion import appear
from desktop.native.weekmodel import WeekModel

if TYPE_CHECKING:
    from desktop.native.layouts.base import LayoutView

WIDTH_SHARE, WIDTH_MIN, WIDTH_MAX = 0.4, 320, 460
# Where the hours open when nothing places the block yet: late afternoon, when homework is done.
OPEN_AT = 15 * 60


def timeline_colours(tokens: dict[str, str]) -> dict[str, str]:
    """A design's colours in the names the timeline paints with."""
    return {
        "window": tokens["surface"],
        "panel": tokens["surface"],
        "hairline": tokens["line"],
        "grid": tokens["line"],
        "muted": tokens["muted"],
        "text": tokens["text"],
        "accent": tokens["accent"],
        "accent_ink": tokens["accent_ink"],
        "error": tokens["danger"],
    }


def shapes_from_week(week: WeekModel, tokens: dict[str, str]) -> list[Shape]:
    from desktop.native.layouts.base import mark_of

    shapes = []
    for item in week.occurrences:
        kind = "Work" if item.work else "Fixed"
        detail = f"{item.start // 60:02d}:{item.start % 60:02d} · {kind}"
        shapes.append(
            Shape(
                block_id=item.block_id,
                day=item.day,
                start=item.start,
                end=item.end,
                title=item.title,
                detail=detail,
                tip=f"{item.title}\n{detail}",
                fill=tokens["card_a"] if item.work else tokens["bg"],
                ink=tokens["text"] if item.work else tokens["bg_ink"],
                outline=tokens["line"],
                edge=mark_of(item.category),
            )
        )
    return shapes


class DayPick(QPushButton):
    """A day's name in the drawer. A drag held over it turns the drawer to that day."""

    def __init__(self, drawer: DropDrawer, day: int) -> None:
        super().__init__(DAYS[day])
        self.setObjectName(f"dropDay{day}")
        self.setCheckable(True)
        self.setAccessibleName(f"Show {DAY_FULL[day]}")
        self.setAcceptDrops(True)
        self._drawer, self._day = drawer, day
        self.clicked.connect(lambda _checked=False: drawer.show_day(day))

    def event(self, event: QEvent) -> bool:  # noqa: A003
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove) and carried(event) is not None:
            self._drawer.show_day(self._day)
            event.acceptProposedAction()  # type: ignore[attr-defined]
            return True
        if event.type() == QEvent.Type.Drop:
            # A day's name is where to look, not where to put it: the hours are for that.
            event.ignore()
            return True
        return super().event(event)


class DropDrawer(QFrame):
    def __init__(self, view: LayoutView) -> None:
        super().__init__(view)
        self.setObjectName("dropDrawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._view = view
        self.day = 0
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 12, 12)
        box.setSpacing(8)
        self.title = QLabel("Drop it at a time")
        self.title.setObjectName("dropTitle")
        box.addWidget(self.title)
        days = QHBoxLayout()
        days.setSpacing(4)
        self.picks = [DayPick(self, day) for day in range(7)]
        for pick in self.picks:
            days.addWidget(pick)
        box.addLayout(days)
        self.hours = Timeline([0])
        self.hours.setObjectName("dropHours")
        self.hours.judge = lambda block_id, from_day, day, start, end: view.judge_span(
            block_id, from_day, day, start, end
        )
        self.hours.minutes_of = view.minutes_of
        self.hours.title_of = view.title_of
        self.hours.dropped.connect(view.placement_requested.emit)
        self.hours.refused.connect(view.refused.emit)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("dropScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.hours)
        self.hours.setFixedHeight(self.hours.full_height())
        box.addWidget(self.scroll, 1)
        self.hide()

    def open(self, block_id: str, from_day: int) -> None:
        """Beside the design, on the day the block is on, or the day the design is showing."""
        scene = self._view.scene
        if scene is None:
            return
        self.hours.palette_colours = timeline_colours(scene.tokens)
        self.hours.set_shapes(shapes_from_week(scene.week, scene.tokens))
        self.hours.today = scene.today
        self.hours.now_min = scene.minute if scene.today is not None else None
        shown = getattr(self._view, "shown_day", None)
        fallback = shown(scene) if callable(shown) else (scene.today if scene.today is not None else 0)
        self.show_day(from_day if 0 <= from_day <= 6 else fallback)
        own = next((item for item in scene.week.occurrences if item.block_id == block_id), None)
        self._look_at(own.start if own is not None and own.day == self.day else OPEN_AT)
        self._place()
        self.show()
        self.raise_()
        appear(self, self._view.motion, shift=40)

    def close_drawer(self) -> None:
        self.hide()

    def show_day(self, day: int) -> None:
        if day == self.day and self.hours.days == [day]:
            return
        self.day = day
        self.hours.days = [day]
        self.hours.update()
        for index, pick in enumerate(self.picks):
            pick.setChecked(index == day)
        self.title.setText(f"Drop it at a time on {DAY_FULL[day]}")

    def _look_at(self, minute: int) -> None:
        top = self.hours.y_of(max(minute - 60, DAY_START_MIN))
        self.scroll.verticalScrollBar().setValue(int(top))

    def _place(self) -> None:
        room = self._view.rect()
        width = int(min(max(room.width() * WIDTH_SHARE, WIDTH_MIN), WIDTH_MAX))
        self.setGeometry(QRect(room.right() - width - 8, 8, width, room.height() - 16))


def drawer_sheet(name: str, tokens: dict[str, str]) -> str:
    """The drawer in the design's colours: a panel laid over the design, its days as small pills."""
    return (
        f"#{name} QFrame#dropDrawer {{ background: {tokens['surface']}; border: 2px solid {tokens['accent']};"
        " border-radius: 14px; }"
        f"#{name} QLabel#dropTitle {{ color: {tokens['text']}; font-weight: 700; }}"
        f"#{name} QPushButton#dropDay0, #{name} QPushButton#dropDay1, #{name} QPushButton#dropDay2,"
        f" #{name} QPushButton#dropDay3, #{name} QPushButton#dropDay4, #{name} QPushButton#dropDay5,"
        f" #{name} QPushButton#dropDay6 {{ background: {tokens['bg']}; color: {tokens['bg_ink']};"
        f" border: 1px solid {tokens['line']}; border-radius: 10px; padding: 3px 6px; min-height: 0; }}"
        f"#{name} QPushButton#dropDay0:checked, #{name} QPushButton#dropDay1:checked,"
        f" #{name} QPushButton#dropDay2:checked, #{name} QPushButton#dropDay3:checked,"
        f" #{name} QPushButton#dropDay4:checked, #{name} QPushButton#dropDay5:checked,"
        f" #{name} QPushButton#dropDay6:checked {{ background: {tokens['accent']};"
        f" color: {tokens['accent_ink']}; border-color: {tokens['accent']}; }}"
        f"#{name} QScrollArea#dropScroll {{ background: transparent; border: none; }}"
    )
