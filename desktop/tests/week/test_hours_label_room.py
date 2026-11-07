"""The hours leave room for their clock words in every design: the column beside them is as wide as the
widest hour word and the time-now pill on the student's clock and text size, a changed clock format or
a minute passing makes it again, and Mission names fewer hours when the words are wide.

How the labels look (fit inside their boxes, never cut by an edge, never running together) is judged on
the pictures (pictures/week_clock.py, screen week.hour-labels-and-now-pill)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.fonts import at_scale, time_font, weighted
from desktop.native.hours.geometry import Axis
from desktop.native.hours.zoom import HoursScroll
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.tokens import WEIGHT_STRONG
from desktop.native.weekmodel import clock_label
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_clock import DESIGNS, hours_scroll, written_clock_words  # noqa: F401
from desktop.tests.window_support import qapp, still  # noqa: F401


def label_font(scroll: HoursScroll):
    canvas = scroll.canvas
    base = canvas.font()
    return at_scale(time_font(base), "caption", canvas.painter.scale(base))


def room_for_hours(scroll: HoursScroll) -> float:
    """The widest hour word on the student's clock and text size, and the margin the words keep."""
    tracks = scroll.canvas.tracks
    first = min(track.first for track in tracks)
    last = max(track.last for track in tracks)
    metrics = QFontMetricsF(label_font(scroll))
    return (
        max(
            metrics.horizontalAdvance(clock_label(minute))
            for minute in range(-(-first // 60) * 60, last + 1, 60)
        )
        + 8
    )


def room_for_the_pill(scroll: HoursScroll) -> float:
    """The time now written in bold on a pill, with its margin."""
    metrics = QFontMetricsF(weighted(label_font(scroll), WEIGHT_STRONG))
    return metrics.horizontalAdvance(clock_label(scroll.canvas.now_min)) + 14


def wait_for_room(qapp: QApplication, scroll: HoursScroll, said: str) -> None:
    wait_until(
        qapp,
        lambda: scroll.canvas.gutter + 0.5 >= room_for_hours(scroll),
        what=lambda: f"{said}: gutter {scroll.canvas.gutter} for words needing {room_for_hours(scroll)}",
    )


def wait_for_the_pill(qapp: QApplication, scroll: HoursScroll, minute_now: int, said: str) -> None:
    wait_until(
        qapp,
        lambda: (
            scroll.canvas.now_min == minute_now and scroll.canvas.gutter + 0.5 >= room_for_the_pill(scroll)
        ),
        what=lambda: f"{said}: gutter {scroll.canvas.gutter} for a pill needing {room_for_the_pill(scroll)}",
    )


def show(window: NativeWindow, design: str, clock: str, text_size: str, window_px: int) -> None:
    session = window.session
    session.preferences = {**session.preferences, "clock_24h": clock == "24h"}
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._look = sanitize_look({"knobs": {"text": text_size}})
    window._apply_appearance()
    window.resize(window_px, 800)
    window._on_week()


@pytest.mark.parametrize("design", DESIGNS)
@pytest.mark.parametrize("clock", ["12h", "24h"])
@pytest.mark.parametrize("text_size", ["normal", "large"])
@pytest.mark.parametrize("window_px", [810, 1280])
def test_the_hour_column_is_wide_enough_for_its_words_after_every_change_of_clock(
    qapp: QApplication, window: NativeWindow, design: str, clock: str, text_size: str, window_px: int
) -> None:
    show(window, design, clock, text_size, window_px)
    session = window.session
    for chosen in ("24h", "12h", clock):
        # What Settings does when the student picks a format.
        session.preferences = {**session.preferences, "clock_24h": chosen == "24h"}
        window._apply_appearance()
        window._sync_chrome()
        still(window)
        scroll = hours_scroll(window)
        if scroll.axis is not Axis.DOWN:
            # Time runs across: the words sit above the lanes, with no column beside them.
            continue
        wait_for_room(qapp, scroll, f"{design} {chosen} {text_size} {window_px}")


@pytest.mark.parametrize("design", ["classic", "timeline"])
def test_these_designs_keep_their_hours_in_a_column_beside_the_blocks(
    qapp: QApplication, window: NativeWindow, design: str
) -> None:
    show(window, design, "12h", "large", 810)
    still(window)
    scroll = hours_scroll(window)
    assert scroll.axis is Axis.DOWN
    assert scroll.canvas.gutter > 0


@pytest.mark.parametrize("design", DESIGNS)
def test_a_new_text_size_gives_the_hours_the_room_their_words_need(
    qapp: QApplication, window: NativeWindow, design: str
) -> None:
    session = window.session
    session.preferences = {**session.preferences, "clock_24h": False}
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window.resize(810, 800)
    for text_size in ("normal", "large", "small", "large"):
        window._look = sanitize_look({"knobs": {"text": text_size}})
        window._apply_appearance()
        window._on_week()
        still(window)
        scroll = hours_scroll(window)
        if scroll.axis is not Axis.DOWN:
            continue
        wait_for_room(qapp, scroll, f"{design} {text_size}")


def test_choosing_a_clock_format_tells_the_hours_of_every_design(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    session.preferences = {**session.preferences, "clock_24h": True}
    window._sync_chrome()
    scrolls = window.planner.findChildren(HoursScroll)
    assert scrolls, "no hours in any design"
    told: list[HoursScroll] = []
    for scroll in scrolls:
        scroll.canvas.labels_changed.connect(lambda scroll=scroll: told.append(scroll))
    session.preferences = {**session.preferences, "clock_24h": False}
    window._sync_chrome()
    assert {id(scroll) for scroll in told} >= {id(scroll) for scroll in scrolls}


def test_the_hours_make_room_again_when_the_time_now_moves(qapp: QApplication, window: NativeWindow) -> None:
    canvas = hours_scroll(window).canvas
    told: list[int] = []
    canvas.labels_changed.connect(lambda: told.append(1))
    canvas.set_clock(canvas.today, 12 * 60 + 58)
    assert len(told) == 1
    canvas.set_clock(canvas.today, 12 * 60 + 58)
    assert len(told) == 1, "the same minute again changes nothing"
    canvas.set_clock(canvas.today, 12 * 60 + 59)
    assert len(told) == 2


@pytest.mark.parametrize("text_size", ["normal", "large"])
def test_the_column_holds_the_time_now_pill_as_the_minutes_pass_to_its_widest(
    qapp: QApplication, window: NativeWindow, text_size: str
) -> None:
    """The pill is written in 600, wider than an hour word, and 12:58 PM is as wide as it gets; the
    column is first made at 9:05 AM, where it is narrower."""
    day = CLOCK.now()
    show(window, "classic", "12h", text_size, 810)
    for hour, minute in ((9, 5), (12, 58)):
        CLOCK.set(datetime.combine(day.date(), day.time().replace(hour=hour, minute=minute)))
        if (hour, minute) == (9, 5):
            window._sync_chrome()
            window._on_week()
        else:
            window._refresh_layout()
        still(window)
        scroll = hours_scroll(window)
        assert scroll.canvas.painter.now_in_gutter
        wait_for_the_pill(qapp, scroll, hour * 60 + minute, f"{hour}:{minute:02d} {text_size}")


def hour_words_on(qapp: QApplication, window: NativeWindow, written: list[str]) -> list[str]:
    """The hour words (not the time now) the hours write once they have settled."""
    still(window)
    scroll = hours_scroll(window)

    def drawn() -> bool:
        written.clear()
        scroll.canvas.grab()
        return bool(written)

    wait_until(qapp, drawn, what="the hours writing their words")
    return [words for words in written if words.endswith(":00") or ":00 " in words]


def test_mission_names_fewer_hours_when_the_words_are_wide(
    qapp: QApplication,
    window: NativeWindow,
    written_clock_words: list[str],  # noqa: F811
) -> None:
    # A minute that is not on the hour, so the pill is never taken for an hour word.
    CLOCK.set(CLOCK.now().replace(hour=19, minute=37))
    show(window, "mission", "24h", "normal", 810)
    narrow = hour_words_on(qapp, window, written_clock_words)
    show(window, "mission", "12h", "large", 810)
    wide = hour_words_on(qapp, window, written_clock_words)
    assert narrow, "Mission wrote no hours"
    assert wide, "Mission wrote no hours at Large on the 12-hour clock"
    assert len(wide) < len(narrow), (narrow, wide)
