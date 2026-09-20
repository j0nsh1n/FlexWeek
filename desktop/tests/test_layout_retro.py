"""Retro desktop: windows that close, come back from the taskbar, and drag by their title bars."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK, block

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea, QWidget

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.layouts.retro import RetroView
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week, minute_of


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-retro-test"])
    yield application


def scene(clock: str = "13:40", blocks: list[dict] | None = None, **chosen: str) -> Scene:
    options = {**options_for(None, "retro"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    week = build_week(WEEK, blocks or BLOCKS, HOMEWORK, TRACE)
    return Scene(week, 3, minute_of(clock), options, tokens_for("retro", options["colour"], palette))


def shown(
    qapp: QApplication,
    width: int = 1366,
    height: int = 720,
    blocks: list[dict] | None = None,
    **chosen: str,
) -> RetroView:
    view = RetroView()
    view.resize(width, height)
    view.show_week(scene(blocks=blocks, **chosen))
    view.show()
    qapp.processEvents()
    return view


def windows(view: RetroView) -> list[str]:
    return sorted(
        item.objectName() for item in view.findChildren(QFrame) if item.property("role") == "window"
    )


def test_three_windows_open_and_the_taskbar_says_so(qapp: QApplication) -> None:
    view = shown(qapp)
    assert windows(view) == ["retroWindow-next", "retroWindow-notes", "retroWindow-week"]
    tasks = [view.findChild(QPushButton, f"retroTask-{key}") for key in ("week", "notes", "next")]
    assert [(task.text(), task.property("open")) for task in tasks] == [
        ("Week.exe", "true"),
        ("deadlines.txt", "true"),
        ("Up next", "true"),
    ]
    assert view.findChild(QLabel, "retroClock").text() == "13:40"


def test_a_window_closes_and_the_taskbar_brings_it_back(qapp: QApplication) -> None:
    view = shown(qapp)
    view.findChild(QPushButton, "retroClose-notes").click()
    assert windows(view) == ["retroWindow-next", "retroWindow-week"]
    assert view.findChild(QPushButton, "retroTask-notes").property("open") == "false"
    view.findChild(QPushButton, "retroTask-notes").click()
    assert "retroWindow-notes" in windows(view)


def test_ok_dismisses_up_next_and_it_says_what_is_coming(qapp: QApplication) -> None:
    view = shown(qapp)
    assert view.findChild(QLabel, "retroNextText").text() == "Dinner starts at 18:00, in 4 h 20 min."
    view.findChild(QPushButton, "retroNextOk").click()
    assert windows(view) == ["retroWindow-notes", "retroWindow-week"]


def test_a_window_drags_by_its_title_bar_and_stays_where_it_was_put(qapp: QApplication) -> None:
    view = shown(qapp)
    frame = view.findChild(QFrame, "retroWindow-notes")
    start = frame.pos()
    bar = view.findChild(QLabel, "retroTitle-notes")
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=QPoint(20, 8))
    QTest.mouseMove(bar, QPoint(20 - 150, 8 - 90))
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=QPoint(20 - 150, 8 - 90))
    moved = view.findChild(QFrame, "retroWindow-notes").pos()
    assert (moved.x(), moved.y()) == (start.x() - 150, start.y() - 90)
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


def test_every_weekday_is_reachable_when_the_desk_is_narrow(qapp: QApplication) -> None:
    weekend = BLOCKS + [
        block(
            "shift",
            "locked",
            [5],
            "09:00",
            240,
            title="Saturday shift at the cafe",
            category="extra",
        ),
        block(
            "choir",
            "locked",
            [6],
            "10:00",
            180,
            title="Sunday choir practice and coffee",
            category="extra",
        ),
    ]
    view = shown(qapp, 1024, 640, blocks=weekend)
    week = view.findChild(QFrame, "retroWindow-week")
    desk = view.findChild(QWidget, "retroDesk")
    assert week.width() <= desk.width()
    assert 0 <= week.x() <= max(desk.width() - 60, 0)
    pane = view.findChild(QScrollArea, "retroWeekPane")
    assert pane is not None
    assert pane.horizontalScrollBar().maximum() > 0
    for day in range(7):
        head = view.findChild(QLabel, f"retroDay{day}")
        pane.ensureWidgetVisible(head)
        qapp.processEvents()
        port = pane.viewport()
        left = head.mapTo(port, QPoint(0, 0)).x()
        assert left < port.width()
        assert left + head.width() > 0


def test_the_notepad_flags_the_squeezed_and_the_unplaced(qapp: QApplication) -> None:
    view = shown(qapp)
    lines = [view.findChild(QPushButton, f"retroNote{index}").text() for index in range(3)]
    assert [line[:2] for line in lines] == ["!!", " !", "??"]
    assert lines[2].split() == ["??", "Poster-1", "not", "placed", "yet"]


def test_closing_the_notepad_cannot_hide_what_has_no_time(qapp: QApplication) -> None:
    view = shown(qapp, windows="week")
    assert windows(view) == ["retroWindow-week"]
    waiting = view.findChild(QPushButton, "retroWaiting0")
    assert (waiting.text(), waiting.toolTip()) == (
        "Poster-1 (2 h)",
        "There is no slot left before this deadline.",
    )


def test_option_colours_repaint_the_desktop_and_the_title_bars(qapp: QApplication) -> None:
    def seen(view: RetroView) -> tuple[str, str]:
        bar = view.findChild(QLabel, "retroTitle-week")
        return view.grab().toImage().pixelColor(
            2, view.height() // 2
        ).name(), bar.grab().toImage().pixelColor(2, 2).name()

    assert seen(shown(qapp)) == ("#008080", "#000080")
    assert seen(shown(qapp, colour="plum")) == ("#5b2a6e", "#4b0082")
