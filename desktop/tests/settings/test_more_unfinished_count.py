"""The count on More is the one count (P1 rule d and guard 6).

The Unfinished badge, More's Unfinished row, its panel and the rail's Not placed yet all read the
engine's time-still-needed list. The count is a pill painted over More's corner: it never adds a bar
above the week. That the pill never changes the size the top bar sees, and how it reads on the bar, are
the pictures settings.more_count_none, settings.more_count_two and settings.more_count_pill.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_there_is_no_bar_above_the_week_for_the_count(window: NativeWindow) -> None:
    assert window.findChild(QPushButton, "unfinishedBadge") is None
    assert not hasattr(window, "unfinished_badge")
    assert not hasattr(window.session, "homework_time_needed_elsewhere")






