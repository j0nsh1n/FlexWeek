"""The week grid under a real mouse: the events Qt delivers to the table's viewport, in order.

No other test sends a mouse event to WeekTable, so nothing here was covered. Expected results come
from the web calendar (frontend/app.js, bindDayLane), which is the reference for these gestures.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame

    from desktop.native.widgets import WeekTable

WEEK = "2026-09-14"
LEFT = "left"
NONE = "none"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-mouse-test"])
    yield application


def fixed(block_id: str, start: str, duration_min: int, day: int = 0, **fields: object) -> dict:
    return {
        "id": block_id,
        "title": block_id.title(),
        "kind": "locked",
        "start": start,
        "duration_min": duration_min,
        "days": [day],
        **fields,
    }


def week(qapp: QApplication, blocks: list[dict]) -> WeekTable:
    table = WeekTable()
    # Tall enough that every 15-minute row is on screen, so a drag never depends on scrolling.
    table.resize(1200, 2400)
    table.set_week(WEEK, blocks, None)
    table.show()
    qapp.processEvents()
    return table


def row_of(hhmm: str) -> int:
    return (int(hhmm[:2]) * 60 + int(hhmm[3:]) - 6 * 60) // 15


def cell(table: WeekTable, hhmm: str, day: int) -> QPoint:
    row = row_of(hhmm)
    return QPoint(
        table.columnViewportPosition(day) + 30, table.rowViewportPosition(row) + table.rowHeight(row) // 2
    )


def send(table: WeekTable, kind: QEvent.Type, pos: QPoint, held: str) -> None:
    viewport = table.viewport()
    buttons = Qt.MouseButton.LeftButton if held == LEFT else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(viewport.mapToGlobal(pos)),
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, event)


def double_click(table: WeekTable, pos: QPoint) -> None:
    # What Qt delivers for a double-click: the second press arrives as MouseButtonDblClick.
    send(table, QEvent.Type.MouseButtonPress, pos, LEFT)
    send(table, QEvent.Type.MouseButtonRelease, pos, NONE)
    send(table, QEvent.Type.MouseButtonDblClick, pos, LEFT)
    send(table, QEvent.Type.MouseButtonRelease, pos, NONE)


def test_double_clicking_a_fixed_block_opens_it(qapp: QApplication) -> None:
    """The web opens the editor on dblclick (app.js, lane "dblclick" listener).

    The table's press handler kept the event from Qt, so Qt never learned which cell was pressed and
    turned every double-click back into a plain press. Nothing opened, and nothing said why.
    """
    table = week(qapp, [fixed("soccer", "07:00", 60)])
    opened: list[str] = []
    moved: list[tuple] = []
    table.block_activated.connect(opened.append)
    table.times_changed.connect(lambda *args: moved.append(args))
    for hhmm in ("07:00", "07:15", "07:45"):
        opened.clear()
        double_click(table, cell(table, hhmm, 0))
        assert opened == ["soccer"], f"double-click on the {hhmm} row"
    assert moved == [], "a double-click is not a drag"


def test_double_clicking_a_shared_cell_asks_once_which_block(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import desktop.native.widgets as widgets

    menus: list[list[str]] = []

    class RecordingMenu(widgets.QMenu):
        def exec(self, *args: object) -> None:
            menus.append([action.text() for action in self.actions()])

    monkeypatch.setattr(widgets, "QMenu", RecordingMenu)
    table = week(qapp, [fixed("band", "07:00", 60, day=2), fixed("tutoring", "07:00", 60, day=2)])
    double_click(table, cell(table, "07:15", 2))
    assert menus == [["Band", "Tutoring"]]


def homework_block(block_id: str, start: str, day: int) -> dict:
    return {**fixed(block_id, start, 60, day), "kind": "flexible", "assignment_id": "hw-" + block_id}


def drag(table: WeekTable, start: QPoint, end: QPoint, *, release: bool = True) -> None:
    send(table, QEvent.Type.MouseButtonPress, start, LEFT)
    middle = QPoint((start.x() + end.x()) // 2, (start.y() + end.y()) // 2)
    send(table, QEvent.Type.MouseMove, middle, LEFT)
    send(table, QEvent.Type.MouseMove, end, LEFT)
    if release:
        send(table, QEvent.Type.MouseButtonRelease, end, NONE)


def test_a_dragged_block_shows_where_it_will_land_and_can_change_day(qapp: QApplication) -> None:
    """The span was worked out and never drawn, and a move could not leave its day."""
    table = week(qapp, [homework_block("essay", "18:00", 2)])
    moved: list[tuple] = []
    table.times_changed.connect(lambda *args: moved.append(args))
    # By its middle: the top and bottom rows are the resize handles.
    drag(table, cell(table, "18:30", 2), cell(table, "19:30", 3), release=False)
    ghost = table.findChild(QFrame, "dragGhost")
    assert ghost is not None and ghost.isVisible()
    assert ghost.geometry().intersects(table.visualRect(table.model().index(row_of("19:00"), 3)))
    send(table, QEvent.Type.MouseButtonRelease, cell(table, "19:30", 3), NONE)
    assert not ghost.isVisible()
    assert moved == [("essay", 3, 19 * 60, 20 * 60)]


def test_a_drop_over_a_fixed_block_is_refused_with_a_reason(qapp: QApplication) -> None:
    table = week(qapp, [homework_block("essay", "18:00", 2), fixed("soccer", "16:00", 90, 3)])
    moved: list[tuple] = []
    refused: list[str] = []
    table.times_changed.connect(lambda *args: moved.append(args))
    table.move_refused.connect(refused.append)
    drag(table, cell(table, "18:30", 2), cell(table, "16:30", 3))
    assert moved == []
    assert refused == ["Soccer is at that time, so it stayed where it was."]


def test_a_drop_past_the_due_time_is_refused(qapp: QApplication) -> None:
    table = week(qapp, [homework_block("essay", "18:00", 2)])
    table.due_point = lambda block_id: (2, 20 * 60) if block_id == "essay" else None
    refused: list[str] = []
    table.move_refused.connect(refused.append)
    drag(table, cell(table, "18:30", 2), cell(table, "18:30", 4))
    assert refused == ["That ends after it is due, so it stayed where it was."]


def test_escape_lets_go_of_a_drag(qapp: QApplication) -> None:
    table = week(qapp, [homework_block("essay", "18:00", 2)])
    moved: list[tuple] = []
    table.times_changed.connect(lambda *args: moved.append(args))
    drag(table, cell(table, "18:30", 2), cell(table, "19:30", 2), release=False)
    QTest.keyClick(table, Qt.Key.Key_Escape)
    send(table, QEvent.Type.MouseButtonRelease, cell(table, "19:30", 2), NONE)
    assert moved == []
    assert not table.findChild(QFrame, "dragGhost").isVisible()
