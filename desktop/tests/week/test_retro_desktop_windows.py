"""Retro desktop, Windows 98 as it was drawn: the windows on the desk, the taskbar, the Start button and
the desktop icons do what they say or nothing at all, and Up next is a dialog that OK dismisses."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.retro import Zoom, arrange, up_next  # noqa: E402
from desktop.native.motion import apply_ui_effects  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_retro import NBSP, scene, shown, task, text, windows  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-retro-test"])
    yield application


def test_three_windows_open_and_the_taskbar_says_so(qapp: QApplication) -> None:
    view = shown(qapp)
    assert windows(view) == ["retroWindow-next", "retroWindow-notes", "retroWindow-week"]
    tasks = [task(view, key) for key in ("week", "notes", "next")]
    assert [(made.text(), made.property("open")) for made in tasks] == [
        ("Week.exe", "true"),
        ("deadlines.txt", "true"),
        ("Up next", "true"),
    ]
    # Windows 98 presses in the button of the window in front alone.
    assert [made.sunk for made in tasks] == [True, False, False]
    assert text(view, "retroClock") == "13:40"
    assert text(view, "retroTitle-notes") == "deadlines.txt - Notepad"


def test_a_window_closes_and_the_taskbar_brings_it_back(qapp: QApplication) -> None:
    view = shown(qapp)
    view.findChild(QPushButton, "retroClose-notes").click()
    assert windows(view) == ["retroWindow-next", "retroWindow-week"]
    assert task(view, "notes").property("open") == "false"
    task(view, "notes").click()
    assert "retroWindow-notes" in windows(view)


def test_a_window_opens_with_windows_98s_zoom_rectangle_within_the_levels(qapp: QApplication) -> None:
    """The title bar of a window opened from the taskbar flies out from its button to where the
    window's lands, and the window shows there. Under Reduce it fades in instead, and with
    animations off it is simply there. Live at once in every level."""
    try:
        for level in ("normal", "reduce", "off"):
            apply_ui_effects(level)
            view = shown(qapp)
            view.findChild(QPushButton, "retroClose-notes").click()
            task(view, "notes").click()
            notes = view.findChild(QFrame, "retroWindow-notes")
            assert "retroWindow-notes" in windows(view), level
            zooms = [child for child in view.children() if isinstance(child, Zoom)]
            effect = notes.graphicsEffect()
            if level == "normal":
                assert len(zooms) == 1, "a title bar flies out"
                zoom = zooms[0]
                assert zoom.start.top() > zoom.end.top(), "up from the taskbar"
                assert zoom.end == QRectF(QRect(notes.bar.mapTo(view, QPoint(0, 0)), notes.bar.size()))
                assert effect.opacity == 0, "the window waits for its title bar to land"
            elif level == "reduce":
                assert zooms == [] and effect.offset == QPoint() and effect.opacity == 0, "a fade, no zoom"
            else:
                assert zooms == [] and effect is None
            wait_until(
                qapp,
                lambda notes=notes, view=view: notes.graphicsEffect() is None
                and not [child for child in view.children() if isinstance(child, Zoom)],
                what=f"the window finishing its opening at {level}",
            )
    finally:
        apply_ui_effects("normal")


def test_a_taskbar_button_brings_its_window_forward_or_puts_the_one_in_front_away(qapp: QApplication) -> None:
    view = shown(qapp)
    task(view, "notes").click()
    assert "retroWindow-notes" in windows(view)
    assert [task(view, key).sunk for key in ("week", "notes", "next")] == [False, True, False]
    task(view, "notes").click()
    assert "retroWindow-notes" not in windows(view)
    assert task(view, "week").sunk, "the window under it comes to the front"
    task(view, "notes").click()
    assert "retroWindow-notes" in windows(view) and task(view, "notes").sunk


def test_minimise_hides_a_window_and_maximise_fills_the_desktop_and_restores_it(qapp: QApplication) -> None:
    view = shown(qapp)
    week = view.findChild(QFrame, "retroWindow-week")
    desk = view.findChild(QWidget, "retroDesk")
    home = week.geometry()
    maximise = view.findChild(QPushButton, "retroMax-week")
    maximise.click()
    qapp.processEvents()
    assert week.geometry() == desk.rect()
    assert maximise.accessibleName() == "Restore Week.exe"
    maximise.click()
    qapp.processEvents()
    assert week.geometry() == home
    assert maximise.accessibleName() == "Maximise Week.exe"
    view.findChild(QPushButton, "retroMin-week").click()
    assert "retroWindow-week" not in windows(view)
    assert task(view, "week").property("open") == "false"


def test_start_opens_the_apps_own_menu_from_its_corner(qapp: QApplication) -> None:
    view = shown(qapp)
    asked: list[QPoint] = []
    view.menu_requested.connect(asked.append)
    start = view.findChild(QPushButton, "retroStart")
    start.click()
    assert asked == [start.mapToGlobal(QPoint(0, 0))]


def test_the_desktop_icons_open_their_windows_and_the_others_are_only_pictures(qapp: QApplication) -> None:
    view = shown(qapp)
    view.findChild(QPushButton, "retroClose-notes").click()
    notes = view.findChild(QPushButton, "retroIcon1")
    assert notes.text() == "deadlines.txt"
    notes.click()
    assert "retroWindow-notes" in windows(view) and task(view, "notes").sunk
    for index, words in ((2, "Homework"), (3, "Focus timer"), (4, "Recycle Bin")):
        assert view.findChild(QPushButton, f"retroIcon{index}") is None
        assert view.findChild(QWidget, f"retroIcon{index}").accessibleName() == words


def test_the_icons_give_way_before_week_exe_gets_narrow() -> None:
    _homes, icons = arrange(QSize(1280, 708), 212, 1.0)
    assert icons
    _homes, icons = arrange(QSize(1150, 700), 212, 1.2)
    assert not icons


def test_ok_dismisses_up_next_and_it_says_what_is_coming(qapp: QApplication) -> None:
    view = shown(qapp)
    assert text(view, "retroNextTitle") == "Dinner"
    # "in 4 h 20 min" is never broken over two lines.
    assert text(view, "retroNextText") == f"starts at 18:00, in{NBSP}4{NBSP}h{NBSP}20{NBSP}min."
    assert text(view, "retroNextThen") == "Then Essay-1 at 18:45."
    view.findChild(QPushButton, "retroNextOk").click()
    assert windows(view) == ["retroWindow-notes", "retroWindow-week"]


def test_up_next_on_another_week_says_nothing_is_next() -> None:
    other = scene()
    other = Scene(other.week, None, other.minute, other.options, other.tokens)
    assert up_next(other).line == "This is another week, so nothing is next."
    last = up_next(scene("19:00"))
    assert (last.title, last.then) == ("Chem-1", "")
    assert up_next(scene("21:00")).title == "Nothing else scheduled today"


def test_a_window_drags_by_its_title_bar_and_stays_where_it_was_put(qapp: QApplication) -> None:
    view = shown(qapp)
    frame = view.findChild(QFrame, "retroWindow-notes")
    start = frame.pos()
    bar = view.findChild(QLabel, "retroTitle-notes")
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=QPoint(20, 8))
    QTest.mouseMove(bar, QPoint(20 - 150, 8 + 90))
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=QPoint(20 - 150, 8 + 90))
    moved = view.findChild(QFrame, "retroWindow-notes").pos()
    assert (moved.x(), moved.y()) == (start.x() - 150, start.y() + 90)
    view.show_week(scene("13:41"))
    again = view.findChild(QFrame, "retroWindow-notes").pos()
    assert (again.x(), again.y()) == (moved.x(), moved.y())


def test_a_window_cannot_be_dragged_off_the_desktop(qapp: QApplication) -> None:
    view = shown(qapp)
    bar = view.findChild(QLabel, "retroTitle-next")
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=QPoint(10, 8))
    QTest.mouseMove(bar, QPoint(-5000, -5000))
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=QPoint(-5000, -5000))
    spot = view.findChild(QFrame, "retroWindow-next").pos()
    assert (spot.x(), spot.y()) == (0, 0)
