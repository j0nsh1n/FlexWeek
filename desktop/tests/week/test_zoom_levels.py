"""The zoom levels a surface offers, how a remembered level is read back, and that each zoom is
reported once so the window can remember it."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import DAY_SCALE  # noqa: E402
from desktop.native.hours.zoom import Scale, sanitize_zoom  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import SCHOOL, a_day, a_week  # noqa: E402

qapp = support_zoom.qapp  # a fixture is found by its name in the test module


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


def test_a_scale_the_look_file_could_not_keep_is_refused_where_it_is_made() -> None:
    """The look file drops a key it does not recognise when it is read, so a scale named that way
    would zoom and then forget, with nothing said."""
    with pytest.raises(ValueError):
        Scale("mission.week2", (32, 48), 48)
    with pytest.raises(ValueError):
        Scale("one_thing.day", (32, 48), 48)
    assert Scale("mission.week", (32, 48), 48).key == "mission.week"


def test_each_zoom_is_reported_once_so_the_window_can_remember_it(qapp: QApplication) -> None:
    view = a_week(qapp)
    said: list[tuple[str, int]] = []
    view.scroll.zoomed.connect(lambda key, px: said.append((key, px)))
    QTest.mouseClick(view.scroll.buttons.into, Qt.MouseButton.LeftButton)
    QTest.mouseClick(view.scroll.buttons.out, Qt.MouseButton.LeftButton)
    view.scroll.restore({"classic.week": 96})
    assert said == [("classic.week", 64), ("classic.week", 48)], "a restored level is not saved again"
    assert view.scroll.px == 96


def test_a_day_never_draws_fifteen_minutes_under_24_pixels(qapp: QApplication) -> None:
    """A quarter hour is the shortest block, and below 24 pixels it is too short to press. This is a
    size, kept here because it limits which levels the Day may offer."""
    view = a_day(qapp, [SCHOOL], 0)
    for px in DAY_SCALE.levels:
        view.scroll.restore({"classic.day": px})
        track = view.hours.tracks[0]
        assert track.per_minute() * 15 >= 24, f"15 minutes is {track.per_minute() * 15:.1f} px at {px}"
