"""What the button-label checks share: dressing the window in a design, a look and a text size, the room a
button's style leaves for its words, and walking the screens a student sees buttons on."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionButton, QWidget

from desktop.native.look import VIEW_BUTTONS
from desktop.native.settings import SECTIONS
from desktop.native.widgets import (
    AvailabilityDialog,
    BlockDialog,
    ChooseTimeDialog,
    HomeworkDialog,
    LateDialog,
    RoutineDialog,
    SchoolHoursDialog,
)
from desktop.tests.window_support import free, settled

EXEMPT_PROPS = ("step", "segment", "pill", "chip", "small")
# The top bar's four views are segments of one control in a track, so they are exempt like segments.
EXEMPT_NAMES = {"sheetClose", *VIEW_BUTTONS}
LATE_WORDS = "Starting from 14:15 today (Wednesday)."


def dress(qapp: QApplication, w, design: str, preset: str, size: str) -> None:
    w.resize(1280, 860)
    w._layout = {"main": design, "day": "one", "options": {}}
    w._look = {"preset": preset, "knobs": {"text": size}}
    w.session.look = w._look
    w._apply_appearance()
    settled(qapp, w)
    qapp.processEvents()


def words_room(button: QPushButton) -> tuple[int, int]:
    """(width the style leaves for the words, width the words and icon need)."""
    option = QStyleOptionButton()
    button.initStyleOption(option)
    contents = button.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, button)
    # Qt draws each line of a button's words on its own, so the widest line is what must fit.
    lines = button.text().replace("&", "").split("\n")
    need = max(button.fontMetrics().horizontalAdvance(line) for line in lines)
    if not button.icon().isNull():
        need += button.iconSize().width() + 4
    return contents.width(), need


def exempt(button: QPushButton) -> bool:
    return button.objectName() in EXEMPT_NAMES or any(button.property(p) for p in EXEMPT_PROPS)


def visible_buttons(root: QWidget) -> list[QPushButton]:
    return [
        b
        for b in root.findChildren(QPushButton)
        if b.isVisible() and b.text().strip() and b.width() > 0
    ]


def sheet_makers(w) -> dict[str, Callable[[], QWidget]]:
    """The sheets that carry buttons with words, each made on the window `w`."""
    week = w.session.week_start
    waiting = {
        "id": "h1", "title": "Essay", "duration_min": 60, "days": list(range(7)), "assignment_id": "a1"
    }
    return {
        "add-homework": lambda: HomeworkDialog(w, today=week, category="assignments"),
        "block-editor": lambda: BlockDialog(w, day=2, start="16:00", duration_min=60),
        "school-hours": lambda: SchoolHoursDialog(w),
        "choose-a-time": lambda: ChooseTimeDialog(w, waiting, week, list(range(7)), [], None),
        "routines": lambda: RoutineDialog(w, {}, [], week),
        "running-late": lambda: LateDialog(w, LATE_WORDS),
        "study-hours": lambda: AvailabilityDialog(w, {}),
    }


def each_screen(qapp: QApplication, w) -> Iterator[tuple[str, QWidget]]:
    """Yield (screen name, root widget) for the window, every Settings section and the sheets."""
    yield "week", w
    w._open_settings()
    settled(qapp, w)
    for index, section in enumerate(SECTIONS):
        w._settings.nav.setCurrentRow(index)
        qapp.processEvents()
        yield f"settings/{section}", w
    w._close_settings(save=False)
    settled(qapp, w)
    for name, make in sheet_makers(w).items():
        dialog = make()
        dialog.show()
        qapp.processEvents()
        settled(qapp, w)
        yield f"sheet/{name}", dialog
        dialog.hide()
        free(dialog)
