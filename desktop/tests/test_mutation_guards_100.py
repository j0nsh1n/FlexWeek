"""Focused guards for mutation cases that the release's broader UI tests do not distinguish."""

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
    from PySide6.QtWidgets import QApplication

    from backend.month import build_month
    from desktop.native.hours.month import MonthGrid
    from desktop.native.hours.rail import NextCard


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mutation-guards-100"])


def busy_month() -> dict:
    snapshot = build_month("2026-09", [], [])
    snapshot["deadlines"] = [
        {"id": f"due-{index}", "title": f"Task {index}", "category": "assignments", "due": "2026-09-30"}
        for index in range(3)
    ]
    for day in snapshot["days"]:
        day["due_ids"] = [f"due-{index}" for index in range(3)]
    return snapshot


def test_month_opens_at_its_first_row_when_the_grid_scrolls(qapp: QApplication) -> None:
    grid = MonthGrid()
    grid.resize(480, 300)
    grid.set_month(busy_month(), False, "2026-09-16")
    grid.show()
    qapp.processEvents()
    grid.reveal("2026-09-24")
    qapp.processEvents()
    bar = grid.scroll.verticalScrollBar()
    assert bar.maximum() > 0, "the busy month needs to scroll"
    assert bar.value() == 0, "opening a date keeps the month's first row at the top"
    grid.close()


def test_a_next_card_with_nothing_to_say_hides_its_card(qapp: QApplication) -> None:
    card = NextCard()
    assert card.show_next(None, None, None) is False
    assert card.card.isHidden(), "nothing now or next today, so the card takes no room"
    card.deleteLater()
