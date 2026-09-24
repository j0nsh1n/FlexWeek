"""Hours that zoom and scroll: the level a surface shows, the minute that stays put while it changes,
and the short block that must still move when it is pressed.

These send Qt events, so they prove the rules; the rig (scripts/rig/drive.py) zooms and drags with a
real pointer on the real window.
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
    from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
    from PySide6.QtGui import QColor, QImage, QMouseEvent, QRegion, QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    from desktop.native.hours.classic import DAY_SCALE, WEEK_SCALE, ClassicDay, ClassicWeek
    from desktop.native.hours.hand import Gesture, Hand, Verdict
    from desktop.native.hours.zoom import Scale, sanitize_zoom
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import build_week

MONDAY = "2026-09-21"
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "days": [0],
    "start": "08:00",
    "duration_min": 390,
}
QUARTER = {"id": "quiz", "title": "Quiz", "kind": "locked", "days": [3], "start": "16:00", "duration_min": 15}


# The hosts of the hands these tests make. A hand is its host's Qt child and holds no reference of
# its own to it, so the host has to be kept for as long as the hand is used.
HOSTS: list = []


def a_hand() -> Hand:
    host = QWidget()
    HOSTS.append(host)
    return Hand(lambda block_id, from_day, span: Verdict(True, ""), host)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-zoom-test"])


def settle(qapp: QApplication) -> None:
    for _ in range(5):
        qapp.processEvents()


def a_week(qapp: QApplication, blocks: list[dict] | None = None) -> ClassicWeek:
    # Inside the offscreen screen (800 by 800), where QApplication.widgetAt can find it.
    view = ClassicWeek(a_hand())
    view.set_look(None, resolved_palette("system", False, None))
    view.set_week(build_week(MONDAY, blocks or [], {}, None), 3, 15 * 60 + 40)
    view.move(0, 0)
    view.resize(760, 520)
    view.show()
    settle(qapp)
    return view


def a_day(qapp: QApplication, blocks: list[dict], day: int) -> ClassicDay:
    view = ClassicDay(a_hand())
    view.set_look(None, resolved_palette("system", False, None))
    view.move(0, 0)
    view.resize(760, 560)
    view.set_day(build_week(MONDAY, blocks, {}, None), day, 3, 15 * 60 + 40)
    view.show()
    settle(qapp)
    return view


def minute_at(view: ClassicWeek | ClassicDay, y: float) -> float:
    """The minute at a height in the hours' viewport."""
    track = view.hours.tracks[0]
    inside = view.scroll.verticalScrollBar().value() + y
    return track.first + (inside - track.area.top()) / track.per_minute()


def wheel(widget: QWidget, at: QPointF, notches: float, ctrl: bool = True) -> None:
    modifiers = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    event = QWheelEvent(
        at,
        QPointF(widget.mapToGlobal(at.toPoint())),
        QPoint(),
        QPoint(0, round(120 * notches)),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


def test_a_remembered_level_is_read_back_as_one_the_surface_offers() -> None:
    scale = Scale("classic.week", (32, 48, 64), 48)
    assert scale.nearest(64) == 64
    assert scale.nearest(70) == 64, "a level no longer offered is the nearest that is"
    assert scale.nearest(40) == 32, "halfway between two levels is the smaller"
    assert scale.nearest("64") == 48 and scale.nearest(True) == 48 and scale.nearest(None) == 48
    assert scale.step(48, 5) == 64 and scale.step(48, -5) == 32
    assert sanitize_zoom(
        {"classic.week": 64, "classic.day": True, "Bad Key": 64, "bento.week": 9000, "x.y": 7}
    ) == {"classic.week": 64}
    assert sanitize_zoom(["classic.week", 64]) == {}


def test_ctrl_and_the_wheel_zoom_about_the_pointer(qapp: QApplication) -> None:
    view = a_week(qapp)
    port = view.scroll.viewport()
    y = port.height() * 0.7
    before = minute_at(view, y)
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), 1)
    assert view.scroll.px == 64
    assert abs(minute_at(view, y) - before) <= 1, "the minute under the pointer stayed under it"
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), 0.5)
    assert view.scroll.px == 64, "half a notch from a touchpad is not a step yet"
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), 0.5)
    assert view.scroll.px == 96, "two half notches are one step"
    wheel(view.hours, QPointF(300, view.scroll.verticalScrollBar().value() + y), -2)
    assert view.scroll.px == 48
    top = view.scroll.verticalScrollBar().value()
    wheel(view.hours, QPointF(300, top + y), -1, ctrl=False)
    assert view.scroll.px == 48, "without Ctrl the wheel only scrolls"


def test_keys_and_buttons_zoom_about_the_middle_and_stop_at_each_end(qapp: QApplication) -> None:
    view = a_week(qapp)
    middle = view.scroll.viewport().height() / 2
    before = minute_at(view, middle)
    view.hours.setFocus()
    QTest.keyClick(view.hours, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
    assert view.scroll.px == 64
    assert abs(minute_at(view, middle) - before) <= 1
    for _ in range(6):
        QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)
    assert view.scroll.px == WEEK_SCALE.levels[-1]
    assert not view.scroll.buttons.into.isEnabled() and view.scroll.buttons.out.isEnabled()
    QTest.keyClick(view.hours, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert view.scroll.px == WEEK_SCALE.default
    for _ in range(6):
        QTest.keyClick(view.hours, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
    assert view.scroll.px == WEEK_SCALE.levels[0]
    assert not view.scroll.buttons.out.isEnabled()


def test_each_zoom_is_reported_once_so_the_window_can_remember_it(qapp: QApplication) -> None:
    view = a_week(qapp)
    said: list[tuple[str, int]] = []
    view.scroll.zoomed.connect(lambda key, px: said.append((key, px)))
    QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)
    QTest.mouseClick(view.scroll.buttons.out, Qt.MouseButton.LeftButton)
    view.scroll.restore({"classic.week": 96})
    assert said == [("classic.week", 64), ("classic.week", 48)], "a restored level is not saved again"
    assert view.scroll.px == 96


def test_nothing_zooms_while_a_block_is_held(qapp: QApplication) -> None:
    view = a_week(qapp, [SCHOOL])
    view.scroll.scroll_to(9 * 60)
    press = view.hours.mapFromGlobal(view.hours.point_for(0, 10 * 60))
    QTest.mousePress(view.hours, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, press)
    assert view.hours.hand.busy
    view.scroll.zoom_by(1)
    assert view.scroll.px == WEEK_SCALE.default
    view.hours.hand.cancel()


def test_a_day_never_draws_fifteen_minutes_under_24_pixels(qapp: QApplication) -> None:
    view = a_day(qapp, [SCHOOL], 0)
    for px in DAY_SCALE.levels:
        view.scroll.restore({"classic.day": px})
        track = view.hours.tracks[0]
        assert track.per_minute() * 15 >= 24, f"15 minutes is {track.per_minute() * 15:.1f} px at {px}"


def press_kind(view: ClassicWeek | ClassicDay, block_id: str, day: int, share: float) -> Gesture:
    """What pressing a drawn block this far along it and moving a little picks up."""
    rect = view.hours.block_rect(block_id, day)
    assert rect is not None, f"{block_id} is not drawn"
    at = QPoint(rect.center().x(), rect.top() + round(rect.height() * share))
    local = QPointF(view.hours.mapFromGlobal(at))
    held = Qt.MouseButton.LeftButton
    for kind, buttons, point in (
        (QEvent.Type.MouseButtonPress, held, local),
        (QEvent.Type.MouseMove, held, local + QPointF(0, 12)),
        (QEvent.Type.MouseMove, held, local + QPointF(0, 24)),
    ):
        global_at = QPointF(view.hours.mapToGlobal(point.toPoint()))
        event = QMouseEvent(kind, point, global_at, held, buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(view.hours, event)
    preview = view.hours.hand.preview
    view.hours.hand.cancel()
    assert preview is not None, f"pressing {share:.0%} into {block_id} picked nothing up"
    return preview.held.kind


@pytest.mark.parametrize("px", WEEK_SCALE.levels)
def test_a_quarter_hour_on_the_week_moves_from_a_quarter_half_and_three_quarters_in(
    qapp: QApplication, px: int
) -> None:
    view = a_week(qapp, [QUARTER])
    view.scroll.restore({"classic.week": px})
    view.scroll.scroll_to(16 * 60)
    settle(qapp)
    for share in (0.25, 0.5, 0.75):
        assert press_kind(view, "quiz", 3, share) is Gesture.MOVE, f"{share:.0%} at {px} px an hour"


@pytest.mark.parametrize("px", DAY_SCALE.levels)
def test_a_quarter_hour_on_the_day_moves_from_a_quarter_half_and_three_quarters_in(
    qapp: QApplication, px: int
) -> None:
    view = a_day(qapp, [QUARTER], 3)
    view.scroll.restore({"classic.day": px})
    view.scroll.scroll_to(16 * 60)
    settle(qapp)
    for share in (0.25, 0.5, 0.75):
        assert press_kind(view, "quiz", 3, share) is Gesture.MOVE, f"{share:.0%} at {px} px an hour"


def test_an_hour_still_resizes_from_its_edges_at_every_level(qapp: QApplication) -> None:
    hour = {**QUARTER, "duration_min": 60}
    view = a_day(qapp, [hour], 3)
    for px in DAY_SCALE.levels:
        view.scroll.restore({"classic.day": px})
        view.scroll.scroll_to(16 * 60)
        settle(qapp)
        assert press_kind(view, "quiz", 3, 0.02) is Gesture.RESIZE_START, f"top edge at {px}"
        assert press_kind(view, "quiz", 3, 0.97) is Gesture.RESIZE_END, f"bottom edge at {px}"


def test_the_day_names_sit_over_their_columns_beside_a_scroll_bar(qapp: QApplication) -> None:
    view = a_week(qapp)
    assert view.scroll.verticalScrollBar().isVisible()
    for day in range(7):
        name = view.findChild(QWidget, f"weekDayName{day}")
        track = view.hours.track_for(day)
        assert name is not None and track is not None
        over = name.mapToGlobal(name.rect().center()).x()
        column = view.hours.mapToGlobal(track.area.center().toPoint()).x()
        assert abs(over - column) <= 1, f"{name.text()} is {over - column} px off its column"


def test_a_week_keeps_where_it_was_scrolled_when_it_is_shown_again(qapp: QApplication) -> None:
    view = a_week(qapp)
    bar = view.scroll.verticalScrollBar()
    view.set_week(build_week("2026-09-28", [], {}, None), None, None)
    opened_at = bar.value()
    bar.setValue(bar.maximum())
    view.hide()
    view.set_week(build_week("2026-09-28", [SCHOOL], {}, None), None, None)
    view.show()
    settle(qapp)
    assert opened_at != bar.maximum()
    assert bar.value() == bar.maximum(), "the same week jumped back to the morning"


def test_a_week_opened_while_hidden_scrolls_to_now_when_it_is_shown(qapp: QApplication) -> None:
    view = a_week(qapp)
    view.hide()
    view.scroll.verticalScrollBar().setValue(0)
    view.set_week(build_week("2026-10-05", [], {}, None), 2, 12 * 60)
    view.show()
    settle(qapp)
    assert 10 * 60 <= minute_at(view, 0) <= 11 * 60, "a new week opens a little above now"


def dark_in(image: QImage, strip: QRect, left: int) -> int:
    return sum(
        1
        for y in range(strip.top(), strip.bottom())
        for x in range(left, left + 60)
        if QColor(image.pixel(x, y)).lightness() < 90
    )


def test_a_small_repaint_does_not_write_a_long_blocks_name_again(qapp: QApplication) -> None:
    """The name of a block taller than the screen is kept in sight at the top of what shows. A repaint
    of a strip in its middle, as when a message over it goes away, must not write it there too."""
    view = a_day(qapp, [SCHOOL], 0)
    hours = view.hours
    track = hours.track_for(0)
    assert track is not None
    top, bottom = round(track.point_for(8 * 60).y()), round(track.point_for(14 * 60 + 30).y())
    view.scroll.verticalScrollBar().setValue(top - 20)
    strip = QRect(0, (top + bottom) // 2, hours.width(), 40)
    image = QImage(hours.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    hours.render(image, strip.topLeft(), QRegion(strip))
    assert dark_in(image, strip, round(track.area.left()) + 8) == 0


def a_lane_week(qapp: QApplication):
    """Seven lanes whose time runs across, as Mission control's week lays them out, with their names
    kept in a strip on the left."""
    from PySide6.QtCore import QRectF
    from PySide6.QtWidgets import QLabel, QVBoxLayout

    from desktop.native.hours.canvas import BlockPainter, HoursCanvas
    from desktop.native.hours.geometry import Axis, LinearTrack
    from desktop.native.hours.zoom import HoursScroll

    def lanes(area: QRectF) -> list[LinearTrack]:
        tall = area.height() / 7
        return [
            LinearTrack(
                day, QRectF(area.left() + 8, area.top() + day * tall, area.width() - 16, tall), Axis.ACROSS
            )
            for day in range(7)
        ]

    hand = a_hand()
    canvas = HoursCanvas(hand, BlockPainter(resolved_palette("system", False, None)), lanes, header=24)
    scroll = HoursScroll(
        canvas,
        Scale("lanes.week", (32, 48, 64, 96), 48),
        lambda px: 24 * px + 16,
        name="lanes",
        gutter=70,
        axis=Axis.ACROSS,
    )
    names = QWidget()
    column = QVBoxLayout(names)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    for day in range(7):
        label = QLabel(f"Day {day}")
        label.setObjectName(f"laneName{day}")
        column.addWidget(label, 1)
    scroll.set_header(names)
    scroll.move(0, 0)
    scroll.resize(760, 420)
    scroll.show()
    settle(qapp)
    return scroll


def minute_across(scroll, x: float) -> float:
    track = scroll.canvas.tracks[0]
    return track.first + (scroll.horizontalScrollBar().value() + x - track.area.left()) / track.per_minute()


def test_lanes_zoom_about_the_pointer_and_the_plain_wheel_moves_them_through_the_day(
    qapp: QApplication,
) -> None:
    scroll = a_lane_week(qapp)
    assert scroll.verticalScrollBar().maximum() == 0, "the lanes fit the height; only time scrolls"
    x = scroll.viewport().width() * 0.6
    before = minute_across(scroll, x)
    wheel(scroll.canvas, QPointF(scroll.horizontalScrollBar().value() + x, 100), 1)
    assert scroll.px == 64
    assert abs(minute_across(scroll, x) - before) <= 1, "the minute under the pointer stayed under it"
    at = scroll.horizontalScrollBar().value()
    # A real wheel passes from the canvas, which leaves it, to the viewport; a sent one stops where
    # it is sent, so it goes where a real one arrives.
    wheel(scroll.viewport(), QPointF(x, 100), -1, ctrl=False)
    assert scroll.px == 64
    assert scroll.horizontalScrollBar().value() > at, "the wheel moved the lanes on through the day"


def test_lane_names_stay_beside_their_lanes_while_the_hours_scroll(qapp: QApplication) -> None:
    scroll = a_lane_week(qapp)
    scroll.scroll_to(6 * 60, above=0)
    settle(qapp)
    for day in range(7):
        name = scroll.findChild(QWidget, f"laneName{day}")
        lane = scroll.canvas.track_for(day)
        beside = name.mapToGlobal(name.rect().center()).y()
        middle = scroll.canvas.mapToGlobal(lane.area.center().toPoint()).y()
        assert abs(beside - middle) <= 2, f"day {day}'s name is {beside - middle} px off its lane"
        assert name.mapToGlobal(name.rect().topLeft()).x() == scroll.mapToGlobal(scroll.rect().topLeft()).x()
    assert 5 * 60 + 45 <= minute_across(scroll, 0) <= 6 * 60 + 15, "06:00 is at the left"


def test_both_ends_of_a_lanes_day_can_be_reached(qapp: QApplication) -> None:
    scroll = a_lane_week(qapp)
    for level in scroll.scale.levels:
        scroll.restore({"lanes.week": level})
        scroll.canvas.reveal(3, 0, 60)
        settle(qapp)
        assert scroll.canvas.in_view(3, 0), f"00:00 at {level} px an hour"
        scroll.canvas.reveal(3, 23 * 60, 24 * 60)
        settle(qapp)
        assert scroll.canvas.in_view(3, 24 * 60), f"24:00 at {level} px an hour"


def test_a_long_blocks_name_stays_in_sight_on_lanes_scrolled_past_its_start(qapp: QApplication) -> None:
    """As on a column scrolled past a long block's top: School runs 08:00 to 14:30 and the lanes are
    scrolled to 12:00, so its name is written at the left of what shows, not at its start off screen."""
    scroll = a_lane_week(qapp)
    scroll.canvas.set_week(build_week(MONDAY, [SCHOOL], {}, None).occurrences)
    scroll.scroll_to(12 * 60, above=0)
    settle(qapp)
    port = scroll.viewport()
    box = scroll.canvas.block_rect("school", 0)
    assert box is not None
    block = QRect(port.mapFromGlobal(box.topLeft()), box.size())
    assert block.left() < 0 < block.right(), "School's start is scrolled away and its end shows"
    image = port.grab().toImage()
    inked = [
        x
        for x in range(0, 60)
        for y in range(block.top() + 4, block.bottom() - 4)
        if QColor(image.pixel(x, y)).lightness() < 90
    ]
    assert inked, "School's bar shows no name in what shows"
    assert min(inked) <= 8, f"School's name starts {min(inked)} px into what shows"
