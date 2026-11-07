"""The rail's Next card says how long is left in a whole sentence that wraps. That the sentence is not
cut off in Terminal is judged on the pictures in pictures/screens_settings_h2.py."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from shiboken6 import delete

from desktop.native.hours.rail import RAIL_PX, NextCard
from desktop.native.look import pack_stylesheet
from desktop.native.weekmodel import build_week
from desktop.tests.window_support import qapp  # noqa: F401


def test_terminals_next_card_wraps_and_ends_with_the_time_left(qapp: QApplication) -> None:  # noqa: F811
    host = QWidget()
    host.setStyleSheet(pack_stylesheet("light-frost", False, {"preset": "terminal"}))
    card = NextCard(host)
    layout = QVBoxLayout(host)
    layout.addWidget(card)
    host.resize(RAIL_PX, 300)
    school = {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "category": "class",
        "start": "08:00",
        "duration_min": 405,
        "days": [1],
    }
    card.show_next(build_week("2026-09-28", [school], [], None), 1, 620)
    host.show()
    try:
        for _ in range(4):
            qapp.processEvents()
        assert card.when.wordWrap()
        assert card.when.text().endswith("4 h 25 min left")
    finally:
        delete(host)
