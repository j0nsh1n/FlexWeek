"""The Plan and More buttons shorten their words in one order as the window narrows, at both text
sizes: Plan my homework + More, then More becomes icon-only, then Plan homework, then the tiny Plan."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import PLAN_LABEL, PLAN_SHORT, PLAN_TINY, NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import pump, set_text_size
from desktop.tests.window_support import qapp  # noqa: F401

# The steps, in the one order they are taken as the window narrows.
STEPS = [(PLAN_LABEL, "More"), (PLAN_LABEL, ""), (PLAN_SHORT, ""), (PLAN_TINY, "")]
WIDTHS = (1400, 1280, 1100, 1000, 900, 810, 800)


def test_plan_follows_one_shortening_rule_at_every_width_and_text_size(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    assert PLAN_SHORT == "Plan homework", PLAN_SHORT
    for size in ("normal", "large"):
        set_text_size(window, size)
        taken = []
        for width in WIDTHS:
            window.solve_button.setMaximumWidth(16777215)
            window.resize(width, 800)
            pump(qapp, 6)
            words = (window.solve_button.text(), window.more_button.text())
            assert words in STEPS, (size, width, words)
            taken.append(STEPS.index(words))
        assert taken == sorted(taken), (size, "a narrower window went back a step", taken)
