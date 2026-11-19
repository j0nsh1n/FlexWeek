"""An empty day or week says "Nothing planned", everywhere it is shown.

The same words in the engine's planned line are checked in engine/engine/tests/desk_weekmodel.rs
(test_planned_line_uses_length_label).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QListWidget

from desktop.native.calendar import DAY_FULL
from desktop.native.hours.classic import DaySummary
from desktop.native.weekmodel import build_week
from desktop.native.window import NativeWindow
from desktop.tests.window_support import qapp  # noqa: F401

WEEK = "2026-10-12"


def test_a_day_summary_with_nothing_planned_says_so(qapp: QApplication) -> None:  # noqa: F811
    assert DaySummary().text() == "Nothing planned"


def test_an_empty_week_list_says_nothing_planned_for_every_day(qapp: QApplication) -> None:  # noqa: F811
    listing = QListWidget()
    host = SimpleNamespace(
        week_access_list=listing,
        session=SimpleNamespace(planner_view="week"),
        _show_week_list_row=lambda _shown: None,
    )
    NativeWindow._sync_week_access_list(host, build_week(WEEK, []))
    rows = [listing.item(i).text() for i in range(listing.count())]
    assert rows == [f"{name}: Nothing planned" for name in DAY_FULL]
    assert rows[1] == "Tuesday: Nothing planned"
