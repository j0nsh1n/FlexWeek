"""A click on a block opens it, a double-click opens it once, a right-click asks for its menu, and
none of them picks it up."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.hours.hand import Move, SecondClick  # noqa: E402
from desktop.tests.week.support_hand import Rig, hand_time, rig_of  # noqa: E402, F401
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_a_click_on_a_block_opens_it_and_a_drag_only_moves_it(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    point = rig.at(2, 18 * 60 + 30)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, point, True)
    assert rig.said == [], "a press may still become a drag, so nothing opens yet"
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    assert rig.said == [("opened", "essay")]
    assert rig.hand.selection == ("essay", 2)
    rig.said.clear()
    rig.drag(point, rig.at(3, 19 * 60 + 30))
    assert rig.said == [Move("essay", 2, Span(3, 19 * 60, 20 * 60))], "a drag moves and opens nothing"


def test_a_click_on_an_edge_opens_the_block_rather_than_resizing_it(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    edge = rig.canvas.block_rect("essay", 2).top() + 2
    point = QPoint(rig.at(2, 18 * 60).x(), edge)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, point, True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    assert rig.said == [("opened", "essay")]


def test_a_double_click_opens_the_block_once_and_enter_opens_it(
    rig_of: Callable[..., Rig], hand_time: list[float]
) -> None:
    rig = rig_of()
    point = rig.at(2, 18 * 60 + 30)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, point, True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    # The second click comes a moment later, well inside the double-click interval.
    hand_time[0] += 0.05
    rig.send(rig.canvas, QEvent.Type.MouseButtonDblClick, point, True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    assert rig.said == [("opened", "essay")], "the first click opened it; the second opens no other editor"
    QTest.keyClick(rig.canvas, Qt.Key.Key_Return)
    assert rig.said == [("opened", "essay"), ("opened", "essay")]
    assert rig.hand.selection == ("essay", 2)


def test_a_double_clicks_second_click_does_nothing_on_the_editor_its_first_opened(
    qapp: QApplication, rig_of: Callable[..., Rig]
) -> None:
    """The first click opens the editor, so the second lands on it, over whatever is there."""
    rig = rig_of()
    point = rig.at(2, 18 * 60 + 30)
    editor = QDialog(rig.window)
    editor.setModal(True)
    button = QPushButton("Delete", editor)
    pressed: list[bool] = []
    button.pressed.connect(lambda: pressed.append(True))

    def open_editor(_block_id: str) -> None:
        editor.show()
        editor.move(editor.pos() + point - button.mapToGlobal(button.rect().center()))
        qapp.processEvents()

    rig.hand.opened.connect(open_editor)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, point, True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    assert QApplication.activeModalWidget() is editor
    assert button.mapToGlobal(button.rect().center()) == point, "the editor's Delete is under the pointer"
    rig.send(button, QEvent.Type.MouseButtonDblClick, point, True)
    rig.send(button, QEvent.Type.MouseButtonPress, point, True)
    rig.send(button, QEvent.Type.MouseButtonRelease, point, False)
    assert pressed == [], "the second click pressed nothing"
    # The double-click interval is over: its timer's slot runs now rather than after the real interval.
    guards = rig.hand.findChildren(SecondClick)
    assert guards, "the tap left nothing to stop a second click"
    for guard in guards:
        guard.stop()
    rig.send(button, QEvent.Type.MouseButtonPress, point, True)
    rig.send(button, QEvent.Type.MouseButtonRelease, point, False)
    assert pressed == [True], "a click after that is the student's own"
    editor.close()


def test_a_double_click_on_its_own_still_opens_the_block(rig_of: Callable[..., Rig]) -> None:
    """Some input sends a double-click with no click before it; the block opens all the same."""
    rig = rig_of()
    rig.send(rig.canvas, QEvent.Type.MouseButtonDblClick, rig.at(2, 18 * 60 + 30), True)
    assert rig.said == [("opened", "essay")]


def right_click(rig: Rig, at: QPoint, to: QPoint | None = None) -> None:
    """A right press, a move while it is down if `to` is given, the release, and the menu request a
    platform sends with it."""
    rig.right(QEvent.Type.MouseButtonPress, at, True)
    for step in range(1, 9) if to is not None else ():
        rig.right(QEvent.Type.MouseMove, at + (to - at) * step / 8, True)
    rig.right(QEvent.Type.MouseButtonRelease, to or at, False)
    local = rig.canvas.mapFromGlobal(to or at)
    QApplication.sendEvent(rig.canvas, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, to or at))


def test_a_right_click_asks_for_the_blocks_menu_and_never_moves_it(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    rig.hand.select("school", 0)
    right_click(rig, rig.at(2, 18 * 60 + 30), rig.at(3, 19 * 60 + 30))
    assert rig.hand.preview is None and not rig.hand.busy, "a right-drag carries nothing"
    assert rig.said == [], "let go over free time: no menu, and nothing moved"
    assert rig.hand.selection == ("school", 0)
    right_click(rig, rig.at(2, 18 * 60 + 30))
    assert rig.said == [("menu", "essay", 2)]
    assert rig.hand.selection == ("essay", 2), "the block under the pointer becomes the selection"
    right_click(rig, rig.at(6, 12 * 60))
    assert rig.said == [("menu", "essay", 2)], "free time has no menu"
    assert rig.hand.selection == ("essay", 2)
    rig.send(rig.canvas, QEvent.Type.MouseMove, rig.at(3, 19 * 60 + 30), False)
    assert rig.said == [("menu", "essay", 2)] and rig.hand.preview is None


def test_a_block_can_be_found_where_it_is_drawn(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    box = rig.canvas.block_rect("essay", 2)
    assert box is not None and box.contains(rig.at(2, 18 * 60 + 30))
    assert rig.canvas.block_rect("essay", 3) is None
