"""The Animations setting: which level wins, how long and how far each level goes, and the rate the
frames follow."""

from __future__ import annotations

import importlib.util
import os

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    from desktop.native import motion as motion_module
    from desktop.native.look import MOTION_LEVELS
    from desktop.native.motion import (
        EASE_MS,
        LEVELS,
        OVER_MS,
        PAGE_IN_AFTER_MS,
        PAGE_IN_MS,
        PAGE_OUT_MS,
        RISE_PX,
        SEGMENT_MS,
        SLIDE_PX,
        appear,
        apply_ui_effects,
        distance,
        duration,
        motion_level,
        moves,
    )
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize(
    ("preference", "look", "level"),
    [
        ("off", "extra", "off"),
        (None, "extra", "extra"),
        (None, None, "normal"),
        ("fast", "normal", "normal"),
        (None, "reduce", "reduce"),
        ("reduce", "normal", "reduce"),
    ],
)
def test_the_students_setting_wins_over_the_looks_own(preference: object, look: object, level: str) -> None:
    assert motion_level(preference, look) == level


def test_the_four_levels_are_the_ones_preferences_and_custom_looks_store() -> None:
    assert tuple(LEVELS) == MOTION_LEVELS == ("normal", "extra", "reduce", "off")


def test_normal_runs_the_plans_numbers_and_the_other_levels_scale_them() -> None:
    """The page change: 120 ms out, 160 in starting 30 ms after, a 24-pixel slide (at 12 none was
    seen), an 8-pixel rise, Settings in 200 ms and the segment in 160. Reduce keeps every fade at
    Normal's length and moves nothing; More is longer and further; Off is at once."""
    timings = (PAGE_OUT_MS, PAGE_IN_MS, PAGE_IN_AFTER_MS, OVER_MS, SEGMENT_MS)
    normal = [duration(ms, "normal") for ms in timings]
    assert normal == [120, 160, 30, 200, 160]
    assert (distance(SLIDE_PX, "normal"), distance(RISE_PX, "normal")) == (24, 8)
    for ms in normal:
        assert duration(ms, "reduce") == ms
        assert duration(ms, "extra") > ms
        assert duration(ms, "off") == 0
    for px in (SLIDE_PX, RISE_PX):
        assert distance(px, "reduce") == distance(px, "off") == 0
        assert distance(px, "extra") > distance(px, "normal")
    assert [moves(level) for level in MOTION_LEVELS] == [True, True, False, False]


def test_more_is_clearly_longer_than_normal_with_the_standard_ease_at_550_ms() -> None:
    """Planning eases for 220 ms. More is 2.5 times that, 550 ms. Reduce keeps 220 ms and travels
    nowhere. Off is immediate. Page changes and Settings keep their own lengths."""
    assert duration(EASE_MS, "normal") == 220
    assert duration(EASE_MS, "extra") == 550
    assert duration(EASE_MS, "reduce") == 220
    assert duration(EASE_MS, "off") == 0
    assert duration(EASE_MS + 60, "normal") == 280
    assert (distance(SLIDE_PX, "reduce"), distance(RISE_PX, "reduce")) == (0, 0)
    page = (PAGE_OUT_MS, PAGE_IN_MS, PAGE_IN_AFTER_MS, OVER_MS, SEGMENT_MS)
    assert [duration(ms, "normal") for ms in page] == [120, 160, 30, 200, 160]
    for ms in (PAGE_OUT_MS, PAGE_IN_MS, PAGE_IN_AFTER_MS, OVER_MS, SEGMENT_MS, EASE_MS):
        assert duration(ms, "extra") >= 2 * duration(ms, "normal"), ms
    assert distance(SLIDE_PX, "extra") > distance(SLIDE_PX, "normal")


def test_frames_follow_the_screen_and_an_unknown_rate_is_60() -> None:
    """An unknown rate is 60, whose interval is 17 ms, never 0."""
    assert motion_module.frame_interval_ms(180) == round(1000 / 180) == 6
    assert motion_module.frame_interval_ms(360) == 3
    assert motion_module.frame_interval_ms(60) == 17
    assert motion_module.frame_interval_ms(0) == 17
    assert motion_module.frame_interval_ms(-5) == 17
    assert motion_module.frame_interval_ms(59.94) == round(1000 / 59.94)


def test_an_animations_clock_ticks_at_the_rate_of_the_screen_it_is_on(qapp: QApplication) -> None:  # noqa: F811
    apply_ui_effects("normal")
    host = QWidget()
    notice = QLabel("Saved.", host)
    notice.move(10, 10)
    host.resize(200, 80)
    host.show()
    qapp.processEvents()
    appear(notice, "normal")
    clock = notice._motion_running[0]
    rate = notice.screen().refreshRate() if notice.screen() is not None else 0
    assert clock.interval() == motion_module.frame_interval_ms(rate or 0)
    assert clock.interval() >= 1
    host.close()
