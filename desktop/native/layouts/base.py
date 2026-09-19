"""What every layout shares: the signals it may raise, and one way of being told about the week.

A layout is presentation only. It is handed a Scene and draws it; when the student wants something
done it says so with a signal, and the window answers with the behaviour it already has. No layout
adds homework, plans, or finishes anything by itself, so there is one planner, not eight.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel, QLayout, QPushButton, QWidget

from desktop.native.weekmodel import WeekModel


@dataclass(frozen=True)
class Scene:
    """Everything a layout needs to draw. `today` is None when the week on screen is not this week."""

    week: WeekModel
    today: int | None
    minute: int
    options: dict[str, str] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    scale: float = 1.0

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

    layout_id = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("layout" + self.layout_id.title())
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._scene: Scene | None = None

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
        self.render(scene, week_changed)
        again = self.findChild(QWidget, name) if name else None
        if again is not None:
            again.setFocus()

    def render(self, scene: Scene, week_changed: bool) -> None:
        raise NotImplementedError
