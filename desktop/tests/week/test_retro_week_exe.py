"""Retro desktop's Week.exe: seven live columns with the day names pinned over them, the scroll bar drawn
like Windows 98's, what a redraw keeps, the status bar and what a block says at its smallest."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollBar, QWidget  # noqa: E402
from shiboken6 import isValid  # noqa: E402

from desktop.native.hours.canvas import Drawn, Started  # noqa: E402
from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.hours.hand import Hand, Verdict  # noqa: E402
from desktop.native.hours.zoom import HoursScroll  # noqa: E402
from desktop.native.layouts.registry import tokens_for  # noqa: E402
from desktop.native.layouts.retro import (  # noqa: E402
    NOT_PLACED,
    DayHead,
    Mirror,
    RetroPainter,
    RetroView,
    scheme,
)
from desktop.tests.test_weekmodel import BLOCKS, block  # noqa: E402
from desktop.tests.week.support_retro import item_holding, palette_of, scene, shown, text  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-retro-test"])
    yield application


def test_week_has_seven_live_columns_and_pinned_day_names(qapp: QApplication) -> None:
    view = shown(qapp, 1150, 768)
    scroll = view.findChild(HoursScroll, "retroWeekScroll")
    assert scroll is not None
    assert [track.day for track in scroll.canvas.tracks] == list(range(7))
    assert scroll.canvas.hand is view.hand
    assert scroll.horizontalScrollBar().maximum() == 0
    opened: list[str] = []
    view.day_activated.connect(opened.append)
    for day in range(7):
        pick = view.findChild(QPushButton, f"retroDay{day}")
        assert pick.isVisible()
        assert pick.text().startswith(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[day])
        assert pick.mapToGlobal(pick.rect().center()) == scroll.canvas.day_name(day)
    view.findChild(QPushButton, "retroDay6").click()
    assert opened == ["2026-09-20"]


def test_a_narrow_week_names_every_day_alike(qapp: QApplication) -> None:
    """With no room for "Wed 16" in one column, every column says its day alone, not some with the
    date and some without."""
    view = shown(qapp, 800, 700)
    heads = [view.findChild(QPushButton, f"retroDay{day}") for day in range(7)]
    assert [head.parts() for head in heads] == [
        [(name, day == 3)] for day, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    ]
    wide = shown(qapp, 1366, 720)
    assert wide.findChild(QPushButton, "retroDay2").parts() == [("Wed ", False), ("16", True)]


def test_every_weekday_has_a_column_and_the_tray_is_there_when_the_desk_is_narrow(qapp: QApplication) -> None:
    weekend = BLOCKS + [
        block("shift", "locked", [5], "09:00", 240, title="Saturday shift at the cafe", category="extra"),
        block(
            "choir", "locked", [6], "10:00", 180, title="Sunday choir practice and coffee", category="extra"
        ),
    ]
    view = shown(qapp, 1150, 768, blocks=weekend, scale=1.4)
    pane = view.findChild(HoursScroll, "retroWeekScroll")
    assert pane is not None
    for day in range(7):
        assert pane.canvas.track_for(day) is not None
        assert view.findChild(QPushButton, f"retroDay{day}").isVisible()
    assert view.findChild(TrayChip, "retroNoteWaiting0").isVisible()


def test_day_head_fits_runs_once_per_head_for_size_hint(qapp: QApplication) -> None:
    view = shown(qapp, 1366, 720)
    heads = [view.findChild(DayHead, f"retroDay{day}") for day in range(7)]
    assert all(head is not None for head in heads)
    original = DayHead._fits
    counts: dict[int, int] = {}

    def counting_fits(self: DayHead) -> bool:
        counts[id(self)] = counts.get(id(self), 0) + 1
        return original(self)

    DayHead._fits = counting_fits  # type: ignore[method-assign]
    try:
        for head in heads:
            head.sizeHint()
        total = sum(counts.values())
        assert total <= 7, f"expected at most 7 _fits calls, got {total}"

        counts.clear()
        for head in heads:
            head.sizeHint()
        assert sum(counts.values()) == 0, "unchanged heads must not call _fits again"

        heads[0].resize(50, heads[0].height())
        counts.clear()
        heads[0].sizeHint()
        assert counts.get(id(heads[0]), 0) >= 1, "a new width must recompute _fits"
    finally:
        DayHead._fits = original  # type: ignore[method-assign]


def test_the_week_scrolls_on_windows_98s_bar_in_step_with_the_hours(qapp: QApplication) -> None:
    view = shown(qapp)
    scroll = view.findChild(HoursScroll, "retroWeekScroll")
    bar = view.findChild(QWidget, "retroWeekScrollBar")
    assert bar.isVisible()
    assert not scroll.verticalScrollBar().isVisible()
    scroll.verticalScrollBar().setValue(120)
    assert bar.value() == 120
    bar.setValue(200)
    assert scroll.verticalScrollBar().value() == 200


def test_windows_98s_bar_leaves_a_cut_value_for_the_hours_to_keep(qapp: QApplication) -> None:
    """The drawn bar copies the hours' range whenever it changes. Qt says a range changed before it
    cuts the value to it, which is when the hours keep where they were; the drawn bar wrote its own cut
    value back first, and so whoever heard of the range after it saw the hours already moved."""
    host = QWidget()
    source, shown_bar = QScrollBar(host), QScrollBar(host)
    source.setRange(0, 400)
    source.setValue(400)
    Mirror(source, shown_bar, host)
    seen: list[int] = []
    source.rangeChanged.connect(lambda _low, _high: seen.append(source.value()))
    source.setRange(0, 380)
    assert seen == [400]
    assert (source.value(), shown_bar.value(), shown_bar.maximum()) == (380, 380, 380)
    shown_bar.setValue(120)
    assert source.value() == 120, "the student's own scrolling on the drawn bar still moves the hours"


def test_redraw_keeps_each_tabs_scroll_zoom_and_position(qapp: QApplication) -> None:
    view = shown(qapp)
    week = view.findChild(HoursScroll, "retroWeekScroll")
    week.zoom_by(1)
    week.verticalScrollBar().setValue(180)
    view.show_week(scene("13:41"))
    assert view.findChild(HoursScroll, "retroWeekScroll") is week
    assert (week.px, week.verticalScrollBar().value()) == (56, 180)
    view.show_week(scene("13:41", surface="day", iso_day="2026-09-17"))
    day = view.findChild(HoursScroll, "retroDayScroll")
    assert day is not None and day is not week
    assert week.parentWidget() is not None
    view.show_week(scene("13:42"))
    assert view.findChild(HoursScroll, "retroWeekScroll") is week
    assert day.parentWidget() is not None
    assert (week.px, week.verticalScrollBar().value()) == (56, 180)


def test_redraw_takes_the_hours_out_of_their_row_before_keeping_them(qapp: QApplication) -> None:
    """Moved out while Week.exe's row still listed them, the hours made Qt delete the row's item behind
    PySide, whose wrapper for it lived on. What Qt made next at that address reached Python as that
    item, and the rig crashed with a segfault."""
    view = shown(qapp, surface="day", iso_day="2026-09-17")
    window = view.findChild(QFrame, "retroWindow-week")
    hours = view.findChild(QFrame, "retroDayScrollField")
    held = item_holding(window.layout(), hours)
    assert held is not None
    wrapped_as_they_left: list[bool] = []

    class Watch(QObject):
        def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
            if event.type() == QEvent.Type.ChildRemoved and event.child() is hours:
                wrapped_as_they_left.append(isValid(held))
            return False

    watch = Watch()
    window.installEventFilter(watch)
    view.show_week(scene("13:41", surface="day", iso_day="2026-09-17"))
    window.removeEventFilter(watch)
    assert view.findChild(QFrame, "retroDayScrollField") is hours
    assert wrapped_as_they_left == [False]


@pytest.mark.parametrize(
    ("verdict", "expected", "state"),
    [
        (Verdict(True, "Thu 10:00–12:00 · 2 h"), "Thu 10:00–12:00 · 2 h", "ok"),
        (Verdict(False, "After the due date"), "10:00–12:00 · After the due date", "refused"),
    ],
)
def test_status_bar_tracks_the_hands_time_and_verdict(
    qapp: QApplication, verdict: Verdict, expected: str, state: str
) -> None:
    host = QWidget()
    hand = Hand(lambda block_id, from_day, span: verdict, host)
    view = RetroView(hand=hand)
    view.resize(1150, 768)
    view.show_week(scene(windows="week"))
    view.show()
    qapp.processEvents()
    assert text(view, "retroStatus") == "Ready"
    scroll = view.findChild(HoursScroll, "retroWeekScroll")
    scroll.scroll_to(10 * 60)
    qapp.processEvents()
    chip = view.findChild(TrayChip, "retroWaiting0")
    target = scroll.canvas.point_for(3, 10 * 60)
    QTest.mousePress(chip, Qt.MouseButton.LeftButton, pos=chip.rect().center())
    QTest.mouseMove(chip, chip.mapFromGlobal(target))
    assert text(view, "retroStatus") == expected
    assert view.findChild(QLabel, "retroStatus").property("verdict") == state
    assert (hand.preview.span.start, hand.preview.span.end) == (600, 720)
    QTest.mouseRelease(chip, Qt.MouseButton.LeftButton, pos=chip.mapFromGlobal(target))
    assert view.findChild(QLabel, "retroStatus").property("verdict") == "ready"


def test_the_status_bar_says_less_rather_than_cutting_its_words(qapp: QApplication) -> None:
    wide = shown(qapp)
    assert [text(wide, name) for name in ("retroStatusNow", "retroStatusWaiting")] == [
        "Thursday 17 September, 13:40",
        f"1 homework {NOT_PLACED}",
    ]
    narrow = shown(qapp, 800, 700)
    assert text(narrow, "retroStatusWaiting") in (f"1 homework {NOT_PLACED}", f"1 {NOT_PLACED}")


def test_a_week_block_says_its_start_alone_and_day_its_length_too() -> None:
    drawn = Drawn("school", "School", "class", False, Span(3, 480, 870), 0, 1)
    assert Started(**vars(drawn)).times == "08:00"
    colours = scheme(tokens_for("retro", "preset:retro-teal", palette_of("light")))
    assert RetroPainter(colours).measures["show_lengths"] is False
    assert RetroPainter(colours, wide=True).measures["show_lengths"] is True
