"""What every layout shares: the signals it may raise, and one way of being told about the week.

A layout is presentation only. It is handed a Scene and draws it; when the student wants something
done it says so with a signal, and the window answers with the behaviour it already has. No layout
adds homework, plans, or finishes anything by itself, so there is one planner, not eight.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QLayout, QPushButton, QScrollArea, QWidget

from desktop.native.calendar import CATEGORIES
from desktop.native.weekmodel import Occurrence, WeekModel


@dataclass(frozen=True)
class Scene:
    """Everything a layout needs to draw. `today` is None when the week on screen is not this week."""

    week: WeekModel
    today: int | None
    minute: int
    options: dict[str, str] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    scale: float = 1.0
    surface: str = "week"
    month: dict | None = None
    iso_day: str = ""
    dirty: bool = False

    def px(self, size: float) -> int:
        """A size in pixels that follows the student's Text size knob."""
        return max(1, round(size * self.scale))


def empty(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget, inner = item.widget(), item.layout()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif inner is not None:
            empty(inner)


def base_sheet(name: str, tokens: dict[str, str]) -> str:
    """Undo what the app's stylesheet gives every frame, label and button, so a design starts clean.

    QLabel is a QFrame, so the label rule has to come after the frame rule.
    """
    return (
        f"#{name} {{ background: {tokens['bg']}; color: {tokens['bg_ink']}; }}"
        f"#{name} QFrame {{ background: transparent; color: {tokens['text']}; border: none;"
        " padding: 0; border-radius: 0; }"
        f"#{name} QLabel {{ background: transparent; color: {tokens['bg_ink']}; border: none; padding: 0; }}"
    )


def rules(name: str, entries: dict[str, str]) -> str:
    """Design rules, each prefixed with the view's own id.

    Without the prefix `#oneLabel` loses to the reset's `#layoutOne QLabel`, which is an id and a type,
    and the accent colour silently turned white. Every selector in a comma list gets the prefix: with
    only the first one prefixed, the second label of a shared rule went back to the reset's colour.
    """
    return "".join(
        ", ".join(f"#{name} {part.strip()}" for part in selector.split(",")) + f" {{ {body} }}"
        for selector, body in entries.items()
    )


def css(**properties: object) -> str:
    """`css(font_size="13px", color=ink)` is `font-size: 13px; color: ...;`. It keeps a design's rules
    one property to a line instead of one long string."""
    return " ".join(f"{name.replace('_', '-')}: {value};" for name, value in properties.items())


def label(text: str, name: str, *, wrap: bool = False) -> QLabel:
    made = QLabel(text)
    made.setObjectName(name)
    made.setWordWrap(wrap)
    made.setTextFormat(Qt.TextFormat.PlainText)
    return made


def button(text: str, name: str, kind: str = "") -> QPushButton:
    made = QPushButton(text)
    made.setObjectName(name)
    made.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        made.setProperty("kind", kind)
    return made


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def mark_of(category: str) -> str:
    """A category's strong colour, the one the web client paints with."""
    return (CATEGORIES.get(category) or {}).get("mark") or "#94a3b8"


def work_left(scene: Scene) -> int:
    """Placed homework minutes still ahead today. Running late is only offered while there are some."""
    if scene.today is None:
        return 0
    total = 0
    for item in scene.week.on_day(scene.today):
        if item.work and item.live and item.end > scene.minute:
            total += item.end - max(item.start, scene.minute)
    return total


# Mission control wanted 1220 pixels, Clay deck 1148 and Bento 1130. Below this a design gives up a
# column rather than making the student scroll sideways to reach Run plan.
NARROW_WIDTH = 1150


class LayoutView(QWidget):
    add_requested = Signal(str)
    plan_requested = Signal()
    block_activated = Signal(str)
    # The whole homework, not one session: that is the only kind of finishing the product has.
    finished_requested = Signal(str)
    focus_requested = Signal(str, int)
    late_requested = Signal()
    my_day_requested = Signal()
    back_requested = Signal()
    day_activated = Signal(str)

    layout_id = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("layout" + self.layout_id.title())
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._scene: Scene | None = None
        self._was_cramped: bool | None = None

    @property
    def scene(self) -> Scene | None:
        return self._scene

    def show_week(self, scene: Scene) -> None:
        if scene == self._scene:
            return
        week_changed = self._scene is None or scene.week != self._scene.week
        self._scene = scene
        held = QApplication.focusWidget()
        name = held.objectName() if held is not None and held is not self and self.isAncestorOf(held) else ""
        self._was_cramped = self.cramped
        if scene.surface == "month":
            host = self._week_host()
            if host is not None:
                host.hide()
            self.render_month(scene, week_changed)
        else:
            board = getattr(self, "_month_board", None)
            if board is not None:
                board.hide()
            host = self._week_host()
            if host is not None:
                host.show()
            self.render(scene, week_changed)
        again = self.findChild(QWidget, name) if name else None
        if again is not None:
            again.setFocus()

    @property
    def cramped(self) -> bool:
        """Too narrow for this design's full arrangement. Measured on the view, not the window."""
        return 0 < self.width() < NARROW_WIDTH

    def _week_host(self) -> QWidget | None:
        """The week surface to put away when Month is on, so it cannot show through the calendar.

        The first widget in the view's own layout is that surface. A layout that keeps a taskbar or
        extra chrome wraps both in one child so Month hides the week, not one panel named `_board`.
        """
        manager = self.layout()
        if manager is None:
            return None
        for index in range(manager.count()):
            widget = manager.itemAt(index).widget()
            if widget is not None:
                return widget
        return None

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        board = getattr(self, "_month_board", None)
        if board is not None and board.isVisible():
            board.setGeometry(self.rect())
        # Only when the answer changes, so an ordinary resize does not rebuild the whole view.
        if self._scene is not None and self.cramped != self._was_cramped:
            self._was_cramped = self.cramped
            if self._scene.surface == "month":
                self.render_month(self._scene, False)
            else:
                self.render(self._scene, False)

    def render(self, scene: Scene, week_changed: bool) -> None:
        raise NotImplementedError

    def render_month(self, scene: Scene, week_changed: bool) -> None:
        """A chip calendar in this design's colours. Retro and Mission keep this; they only paint."""
        from desktop.native.widgets import MonthGrid

        board = getattr(self, "_month_board", None)
        if board is None:
            board = MonthGrid(self)
            board.setObjectName("layoutMonthBoard")
            board.day_activated.connect(self.day_activated.emit)
            self._month_board = board
        placed = [
            (scene.week.date_of(item.day).isoformat(), item.title, item.category)
            for item in scene.week.occurrences
        ]
        board.set_tokens(scene.tokens)
        board.set_placed(placed)
        board.set_month(scene.month, scene.dirty)
        if scene.iso_day:
            board.reveal(scene.iso_day)
        board.setGeometry(self.rect())
        board.show()
        board.raise_()


def day_buttons(
    view: LayoutView, scene: Scene, item: Occurrence | None, prefix: str, *, upper: bool = False
) -> list[QPushButton]:
    """What a student does while living the day, written once for every day screen: finish the
    homework, start focus, say they are running late, go back to planning."""

    def word(text: str) -> str:
        return text.upper() if upper else text

    made = []
    if scene.options.get("actions") != "hide":
        if item is not None and item.work and item.assignment_id:
            finished = button(word("Homework finished"), f"{prefix}Finished", "main")
            finished.clicked.connect(
                lambda _=False, key=item.assignment_id: view.finished_requested.emit(key)
            )
            focus = button(word("Start focus"), f"{prefix}Focus")
            focus.clicked.connect(
                lambda _=False, entry=item: view.focus_requested.emit(entry.block_id, entry.day)
            )
            made += [finished, focus]
        if work_left(scene):
            late = button(word("Running late"), f"{prefix}Late")
            late.clicked.connect(view.late_requested.emit)
            made.append(late)
    back = button(word("Back to planning"), f"{prefix}Back")
    back.clicked.connect(view.back_requested.emit)
    return [*made, back]


def plan_buttons(view: LayoutView, prefix: str, add_words: str) -> list[QPushButton]:
    """Add homework. Plan my homework and My day live in the top bar in every layout."""
    add = button(add_words, f"{prefix}Add", "main")
    add.clicked.connect(lambda _=False: view.add_requested.emit(""))
    return [add]


def block_button(view: LayoutView, text: str, name: str, block_id: str, kind: str = "row") -> QPushButton:
    """A block as something a keyboard can reach. The `block_id` property is how a test, or a screen
    reader's script, can tell which block a button opens."""
    made = button(text, name, kind)
    made.setProperty("block_id", block_id)
    made.clicked.connect(lambda _=False: view.block_activated.emit(block_id))
    return made


def scrolling(content: QWidget, name: str) -> QScrollArea:
    """A main view shares the window with the planning controls and gets about half its height, so
    whatever does not fit scrolls instead of being cut off."""
    area = QScrollArea()
    area.setObjectName(name)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area
