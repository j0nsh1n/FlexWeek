# ruff: noqa: F811
"""The week page around its hours: when the window's Animations level is applied again."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_a_change_to_the_week_does_not_apply_the_animation_level_again_when_it_is_the_same(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every change to the week passes through _apply_appearance; Qt's effects are set only when the level
    moves."""
    applied: list[str] = []
    window._apply_appearance()
    monkeypatch.setattr("desktop.native.window.apply_ui_effects", applied.append)
    window._on_week()
    window._on_week()
    assert applied == []
    window.session.preferences = {**window.session.preferences, "motion": "off"}
    window._on_week()
    assert applied == ["off"], "a new level is still put on at once"
    window._on_week()
    assert applied == ["off"]
