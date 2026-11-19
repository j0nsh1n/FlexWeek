"""Today's app's rail: what is next, Not placed yet and the focus list left of Day and Week, the
running timer as its first card, the mini month folded away and remembered, the one-go message, and
the window's floor. How the rail looks (widths, gaps, fit) is in pictures/week_material.py."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from desktop.native.window import WINDOW_MIN_WIDTH
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_material import pump
from desktop.tests.window_support import look_file, qapp, settled  # noqa: F401


def test_the_window_is_never_narrower_than_800(qapp, window) -> None:
    assert WINDOW_MIN_WIDTH == 800
    window.resize(650, 720)
    pump(qapp, 3)
    assert window.width() == 800














