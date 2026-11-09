"""Day lists its agenda beside the rail, in order, with a summary line for each kind of thing."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.classic import ClassicDay  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.week.support_hand import a_hand  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_day_lists_its_agenda_in_order_and_keeps_now_on_the_grid(qapp: QApplication) -> None:
    """Day drops its Next band; beside the rail it lists the day, times and lengths, and a summary
    with a dot for each kind of thing. A click on a line opens it."""
    blocks = [
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 405,
            "days": [3],
        },
        {
            "id": "soccer",
            "title": "Soccer practice",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 90,
            "days": [3],
        },
        {
            "id": "dinner",
            "title": "Dinner",
            "kind": "locked",
            "category": "meals",
            "start": "18:30",
            "duration_min": 30,
            "days": [3],
        },
    ]
    hand = a_hand()
    opened: list[str] = []
    hand.opened.connect(opened.append)
    view = ClassicDay(hand)
    view.set_look(None, resolved_palette("system", False, None))
    view.resize(1000, 700)
    view.set_day(build_week("2026-09-21", blocks, {}, None), 3, 3, 15 * 60 + 40)
    view.show()
    qapp.processEvents()
    agenda = view.agenda
    assert agenda.heading.text() == "Agenda"
    assert agenda.sub.text() == "3 things · 8 h 45 min"
    rows = [row.item.title if row.item is not None else "now" for row in agenda.list.rows]
    assert rows == ["School", "Soccer practice", "Dinner"]
    assert view.summary.text() == "School: 6 h 45 min\nActivity: 1 h 30 min\nMeals: 30 min"
    soccer = agenda.list.rows[1].box.center().toPoint()
    QTest.mouseClick(agenda.list, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, soccer)
    assert opened == ["soccer"]
    view.set_day(build_week("2026-09-21", blocks, {}, None), 3, None, None)
    assert [row.item is None for row in agenda.list.rows] == [False] * 3, "no now on a day that is not today"
