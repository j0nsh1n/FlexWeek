"""The Animations setting: which level wins, how long and how far each level goes, and what the level
does to Qt's own menu and tooltip fades."""

from __future__ import annotations

import importlib.util
import os

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from desktop.native.look import MOTION_LEVELS
    from desktop.native.motion import apply_ui_effects
    from desktop.native.motion_level import (
        EASE_MS,
        LEVELS,
        app_level,
        distance,
        duration,
        motion_level,
        moves,
    )
    from desktop.tests.window_support import qapp  # noqa: F401

# Sample timings and distances (Normal's), as a fade, a slide and a rise were.
SAMPLE_MS = (120, 160, 30, 200)
SAMPLE_PX = (24, 8)


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
    """Normal keeps a duration and a distance as given. Reduce keeps every fade at Normal's length and
    moves nothing; More is longer and further; Off is at once."""
    normal = [duration(ms, "normal") for ms in SAMPLE_MS]
    assert normal == list(SAMPLE_MS)
    assert [distance(px, "normal") for px in SAMPLE_PX] == list(SAMPLE_PX)
    for ms in normal:
        assert duration(ms, "reduce") == ms
        assert duration(ms, "extra") > ms
        assert duration(ms, "off") == 0
    for px in SAMPLE_PX:
        assert distance(px, "reduce") == distance(px, "off") == 0
        assert distance(px, "extra") > distance(px, "normal")
    assert [moves(level) for level in MOTION_LEVELS] == [True, True, False, False]


def test_more_is_clearly_longer_than_normal_with_the_standard_ease_at_550_ms() -> None:
    """Planning eases for 220 ms. More is 2.5 times that, 550 ms. Reduce keeps 220 ms and travels
    nowhere. Off is immediate."""
    assert duration(EASE_MS, "normal") == 220
    assert duration(EASE_MS, "extra") == 550
    assert duration(EASE_MS, "reduce") == 220
    assert duration(EASE_MS, "off") == 0
    assert duration(EASE_MS + 60, "normal") == 280
    for ms in (*SAMPLE_MS, EASE_MS):
        assert duration(ms, "extra") >= 2 * duration(ms, "normal"), ms


@pytest.mark.parametrize(
    ("level", "fades", "slides"),
    [("normal", True, True), ("extra", True, True), ("reduce", True, False), ("off", False, False)],
)
def test_the_level_sets_the_menu_and_tooltip_effects_and_the_apps_own_level(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, level: str, fades: bool, slides: bool  # noqa: F811
) -> None:
    """Asked of the calls, not of `isEffectEnabled`: the offscreen platform reports every effect off."""
    asked: dict[Qt.UIEffect, bool] = {}
    record = staticmethod(lambda effect, on=True: asked.update({effect: on}))
    monkeypatch.setattr(QApplication, "setEffectEnabled", record)
    try:
        apply_ui_effects(level)
        assert app_level() == level
        assert asked[Qt.UIEffect.UI_FadeMenu] is fades
        assert asked[Qt.UIEffect.UI_FadeTooltip] is fades
        assert asked[Qt.UIEffect.UI_AnimateCombo] is slides
    finally:
        monkeypatch.undo()
        apply_ui_effects("normal")
