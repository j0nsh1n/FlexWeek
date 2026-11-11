"""The time label beside the now line in Material Week and Day (Jonathan, 2026-11-10): the current time, in
the account's clock format, sits in the hour column at the line's height. It never covers a block, moves
with the line on the clock tick, and says "Current time, <time>" to a screen reader. The colour, size and
corners are judged in the picture review.

Expected values come from the fake clock (Thursday 19:00, then twenty-five minutes later) and from the
layout's relations: the hour column ends where the first day's blocks begin.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF  # noqa: E402
from PySide6.QtGui import QAccessible  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.weekmodel import set_clock_24h  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import named, pump, qml  # noqa: E402
from desktop.tests.sheets.support_material_sheets import bridge, material_week, week_monday  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

THURSDAY = 3
SCREENS = ["week", "day"]


def on_screen(qapp, window: NativeWindow, screen: str) -> QObject:
    """Material on Week, or on Day for Thursday; returns the page whose items the test reads."""
    root = material_week(qapp, window)
    if screen == "week":
        return qml(root, "materialWeek")
    window.session.open_day((week_monday(window) + timedelta(days=THURSDAY)).isoformat())
    bridge(window).showPage("day")
    pump(qapp)
    wait_until(qapp, lambda: root.findChild(QObject, "materialDay") is not None)
    return qml(root, "materialDay")


def label_of(page: QObject) -> QObject:
    found = named(page, "nowLabel")
    assert len(found) == 1, found
    return found[0]


def words(label: QObject) -> str:
    return str(named(label, "nowLabelText")[0].property("text"))


def a11y_name(item: QObject) -> str:
    face = QAccessible.queryAccessibleInterface(item)
    return face.text(QAccessible.Text.Name) if face is not None else ""


def scene_rect(item: QObject) -> tuple[float, float, float, float]:
    top_left = item.mapToScene(QPointF(0, 0))
    bottom_right = item.mapToScene(QPointF(item.width(), item.height()))
    return top_left.x(), top_left.y(), bottom_right.x(), bottom_right.y()


def use_12_hour(qapp, window: NativeWindow) -> None:
    set_clock_24h(False)
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": False}
    window._material_page.publish()
    pump(qapp, 20)


@pytest.mark.parametrize("screen", SCREENS)
def test_the_label_shows_the_time_in_the_24_hour_clock(qapp, window: NativeWindow, screen: str) -> None:
    label = label_of(on_screen(qapp, window, screen))
    assert label.property("visible") is True
    assert words(label) == "19:00"
    assert a11y_name(label) == "Current time, 19:00"


@pytest.mark.parametrize("screen", SCREENS)
def test_the_label_shows_the_time_in_the_12_hour_clock(qapp, window: NativeWindow, screen: str) -> None:
    page = on_screen(qapp, window, screen)
    use_12_hour(qapp, window)
    label = label_of(page)
    assert words(label) == "7:00 PM"
    assert a11y_name(label) == "Current time, 7:00 PM"


@pytest.mark.parametrize("screen", SCREENS)
def test_the_label_sits_in_the_hour_column_at_the_lines_height_and_covers_no_block(
    qapp, window: NativeWindow, screen: str
) -> None:
    page = on_screen(qapp, window, screen)
    label = label_of(page)
    line = named(page, "nowLine")[0]
    left, top, right, bottom = scene_rect(label)
    _line_left, line_top, _line_right, line_bottom = scene_rect(line)
    assert abs((top + bottom) / 2 - (line_top + line_bottom) / 2) <= 2, "at the line's height"
    blocks = named(page, "weekBlock")
    assert blocks
    for block in blocks:
        b_left, b_top, b_right, b_bottom = scene_rect(block)
        apart = right <= b_left or b_right <= left or bottom <= b_top or b_bottom <= top
        assert apart, "the label is over a block"
    assert left >= scene_rect(qml(page, "weekScroller" if screen == "week" else "dayScroller"))[0]


@pytest.mark.parametrize("screen", SCREENS)
def test_the_label_moves_with_the_line_on_the_clock_tick_and_with_zoom(
    qapp, window: NativeWindow, screen: str
) -> None:
    page = on_screen(qapp, window, screen)
    label = label_of(page)
    line = named(page, "nowLine")[0]
    CLOCK.set(CLOCK.now() + timedelta(minutes=25))
    window._tick_material_clock()
    wait_until(qapp, lambda: words(label) == "19:25", what="the label to show the new time")
    assert a11y_name(label) == "Current time, 19:25"
    bridge(window).zoomBy(1)
    pump(qapp, 20)
    _l, top, _r, bottom = scene_rect(label)
    _ll, line_top, _lr, line_bottom = scene_rect(line)
    assert abs((top + bottom) / 2 - (line_top + line_bottom) / 2) <= 2


def test_there_is_no_label_in_the_settings_preview_without_a_line(qapp, window: NativeWindow) -> None:
    """The preview week is passive and shows no time label."""
    root = material_week(qapp, window)
    bridge(window).showPage("settings")
    pump(qapp, 20)
    for label in named(root, "nowLabel"):
        assert label.property("visible") is False


def hour_labels(page: QObject) -> list[QObject]:
    found = named(page, "hourLabel")
    assert len(found) == 24, len(found)
    return found


def shown(item: QObject) -> bool:
    """What the student sees: the hour numbers are hidden by opacity, not by the visible flag."""
    return item.property("visible") is True and float(item.property("opacity")) > 0


def uncovered(page: QObject) -> list[tuple[int, QObject]]:
    """Hour numbers the zoom pill does not sit on (it hides those by its own rule, not the label's)."""
    pills = [scene_rect(pill) for pill in named(page, "weekZoom")]
    margin = 2
    out = []
    for index, number in enumerate(hour_labels(page)):
        left, top, right, bottom = scene_rect(number)
        if not any(
            overlap((left - margin, top - margin, right + margin, bottom + margin), pill) for pill in pills
        ):
            out.append((index, number))
    assert len(out) >= 20, "the pill hides too many numbers for this test to prove anything"
    return out


def overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def clock_at(qapp, window: NativeWindow, page: QObject, scroller: str, hour: int, minute: int) -> QObject:
    """Move the clock, scroll to the top so only the label can hide an hour number, and return the label."""
    CLOCK.set(datetime(2026, 11, 5, hour, minute))
    window._tick_material_clock()
    label = label_of(page)
    wait_until(qapp, lambda: words(label) == f"{hour}:{minute:02d}", what="the label to show the new time")
    qml(page, scroller).setProperty("contentY", 0)
    pump(qapp, 20)
    return label


@pytest.mark.parametrize("screen", SCREENS)
@pytest.mark.parametrize(("hour", "minute"), [(11, 0), (10, 58), (11, 3)])
def test_the_hour_number_under_the_label_is_hidden_and_the_others_stay(
    qapp, window: NativeWindow, screen: str, hour: int, minute: int
) -> None:
    """Hour 11's number is 14 px tall and starts 8 px above its line; the label is about 21 px tall and
    centred on the time's line. At 10:58, 11:00 and 11:03 the two overlap, so only that number goes."""
    page = on_screen(qapp, window, screen)
    scroller = "weekScroller" if screen == "week" else "dayScroller"
    label = clock_at(qapp, window, page, scroller, hour, minute)
    assert shown(label)
    numbers = hour_labels(page)
    assert str(numbers[11].property("text")) == "11:00"
    assert overlap(scene_rect(label), scene_rect(numbers[11])), "the fixture no longer overlaps"
    assert not shown(numbers[11]), "the hour number under the label is still drawn"
    for index, number in uncovered(page):
        if index != 11:
            assert shown(number), f"the number for {index}:00 was hidden"


@pytest.mark.parametrize("screen", SCREENS)
def test_every_hour_number_shows_when_the_label_is_between_two_hours(
    qapp, window: NativeWindow, screen: str
) -> None:
    page = on_screen(qapp, window, screen)
    scroller = "weekScroller" if screen == "week" else "dayScroller"
    label = clock_at(qapp, window, page, scroller, 11, 30)
    for _index, number in uncovered(page):
        assert not overlap(scene_rect(label), scene_rect(number)), "the fixture overlaps an hour number"
        assert shown(number), f"the number {number.property('text')} was hidden"
