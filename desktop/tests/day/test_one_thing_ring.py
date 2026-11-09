"""One thing's countdown ring and the day bar under it: what number the ring shows, how it moves from
one minute to the next, what it does when nothing counts down, and the words the bar is named with.
Where they are drawn is judged on the pictures (desktop/tests/pictures/_day_g02.py)."""

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
    from PySide6.QtWidgets import QApplication, QLabel

    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.one_thing import DayBar, OneThingView, label_minutes
    from desktop.native.layouts.registry import options_for, tokens_for
    from desktop.native.look import resolved_palette
    from desktop.native.motion import apply_ui_effects, duration
    from desktop.native.ring import ARC_MS, CountdownRing
    from desktop.native.weekmodel import build_week, clock_label, minute_of, set_clock_24h
    from desktop.tests.day.support_one_thing import (
        THURSDAY,
        counts,
        full_title,
        ring_of,
        says,
        scene,
        shown,
    )
    from desktop.tests.test_weekmodel import BLOCKS, WEEK


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-one-thing-ring-test"])
    yield application


def held_at(ring: CountdownRing, ms: int) -> float:
    """The share the ring draws `ms` into its ease, held there rather than timed."""
    ring._ease.pause()
    ring._ease.setCurrentTime(ms)
    return ring.left()


def test_the_ring_is_the_hour_ahead_like_a_kitchen_timer(qapp: QApplication) -> None:
    """Twenty minutes to go is a third of the ring from the top; three hours or more is the whole
    ring, and the number turns to hours."""
    assert counts(shown(qapp, "17:40")) == ("20", round(20 / 60, 3))
    assert counts(shown(qapp, "15:20")) == ("2:40", 1.0)
    assert counts(shown(qapp, "15:00")) == ("3", 1.0)
    assert ring_of(shown(qapp, "15:00")).accessibleName() == "3 h until it starts"


@pytest.mark.parametrize("level", ["normal", "extra"])
def test_a_minute_passing_eases_the_ring_down_rather_than_jumping(qapp: QApplication, level: str) -> None:
    """As the mock-up's arc does. The layout is built again each minute, and the new ring carries on
    from what the last one drew. More takes a little longer than Normal."""
    apply_ui_effects(level)
    try:
        view = shown(qapp, "13:40")
        view.show_week(scene("13:41"))
        ring = ring_of(view)
        assert ring.number() == "49", "the number is the new minute's at once"
        assert ring.left() == pytest.approx(50 / 60), "the arc leaves from where it was"
        assert 49 / 60 < held_at(ring, duration(ARC_MS, "normal") // 3) < 50 / 60
        assert held_at(ring, duration(ARC_MS, level)) == pytest.approx(49 / 60)
        assert (ring._ease.duration() > duration(ARC_MS, "normal")) is (level == "extra")
    finally:
        apply_ui_effects("normal")


def test_built_again_mid_ease_the_ring_goes_on_from_where_it_was_drawn(qapp: QApplication) -> None:
    apply_ui_effects("normal")
    view = shown(qapp, "13:40")
    view.show_week(scene("13:41"))
    midway = held_at(ring_of(view), duration(ARC_MS) // 2)
    view.show_week(scene("13:41"))
    assert ring_of(view).left() == pytest.approx(midway)


@pytest.mark.parametrize("level", ["reduce", "off"])
def test_under_reduce_the_ring_is_at_the_new_minute_at_once(qapp: QApplication, level: str) -> None:
    apply_ui_effects(level)
    try:
        view = shown(qapp, "13:40")
        view.show_week(scene("13:41"))
        assert ring_of(view).left() == pytest.approx(49 / 60)
    finally:
        apply_ui_effects("normal")


def test_a_new_countdown_fills_the_ring_at_once_rather_than_sweeping_it_back(qapp: QApplication) -> None:
    """School's last minute, then Dinner three and a half hours off: the arc is not run back round the
    ring, which would read as the clock going backwards."""
    apply_ui_effects("normal")
    view = shown(qapp, "14:29")
    assert counts(view) == ("1", round(1 / 60, 3))
    view.show_week(scene("14:30"))
    assert counts(view) == ("3:30", 1.0)


def test_with_no_countdown_the_ring_has_no_minute_scale_and_says_how_long_is_free(
    qapp: QApplication,
) -> None:
    """The empty state once drew a full minute ring with 0 / 15 / 30 / 45 and twelve ticks though
    nothing counts down, and said "Nothing else scheduled today" twice. At 21:40 nothing is left
    before 22:00."""
    view = shown(qapp, "21:40")
    assert says(view)[0] == "Nothing left today"
    assert full_title(view) == "Nothing else scheduled today"
    assert says(view)[2] == "20 min free"
    assert ring_of(view).scale() == (0, ()), "no minute scale when no countdown runs"
    assert counts(view)[0] == ""
    # With a countdown running the scale is there.
    assert ring_of(shown(qapp, "13:40")).scale() == (12, ("0", "15", "30", "45"))


def test_the_empty_state_keeps_its_old_words_once_the_evening_is_over(qapp: QApplication) -> None:
    view = shown(qapp, "22:30")
    line = view.findChild(QLabel, "oneLine")
    assert line.text() == ""
    assert line.accessibleName() == "Tomorrow starts with School at 08:00"
    assert ring_of(view).scale() == (0, ())


def test_the_day_bar_is_named_for_its_hours_and_for_what_is_on_it(qapp: QApplication) -> None:
    assert label_minutes(6 * 60, 22 * 60) == [6 * 60, 9 * 60, 12 * 60, 15 * 60, 18 * 60, 22 * 60]
    assert shown(qapp, "13:40").findChild(DayBar).painter.caption == "Today, 06:00 to 22:00."
    # Nothing on the day at all says so.
    empty_day = [block for block in BLOCKS if block["id"] == "chem-1"]
    nothing = OneThingView()
    nothing.resize(1200, 820)
    options = options_for(None, "one")
    palette = resolved_palette("light-frost", False, None)
    nothing.show_week(
        Scene(
            build_week(WEEK, empty_day, {}, None),
            THURSDAY,
            minute_of("13:40"),
            options,
            tokens_for("one", options["look"], palette),
        )
    )
    nothing.show()
    qapp.processEvents()
    assert nothing.findChild(DayBar).painter.caption == "Today, 06:00 to 22:00. Nothing planned."


def test_the_day_bar_names_its_times_on_the_12_hour_clock_when_that_is_chosen(qapp: QApplication) -> None:
    set_clock_24h(False)
    caption = shown(qapp, "13:40").findChild(DayBar).painter.caption
    assert caption == f"Today, {clock_label(6 * 60)} to {clock_label(22 * 60)}."
    assert "AM" in caption


def test_option_day_bar_hidden_removes_it(qapp: QApplication) -> None:
    assert shown(qapp, "19:00").findChild(DayBar) is not None
    assert shown(qapp, "19:00", daybar="hide").findChild(DayBar) is None
