"""Homework chips in the rail and the tray shorten their title to the room they have, keep the length
whole, say everything to a screen reader, and say it all again when given room."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.rail import RAIL_PX, Rail  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import Waiting, build_week  # noqa: E402
from desktop.tests.week.support_hand import a_hand  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_a_rail_chip_shortens_its_title_to_the_rail_and_keeps_its_length(qapp: QApplication) -> None:
    """The rail is narrower than a long title. A chip there shortens the title, never the length,
    never widens the rail, and says the whole title to a screen reader and in its tooltip; given
    room again it says it all."""
    title = "Science poster on the water cycle for Ms Alvarez"
    poster = {
        "id": "poster-1",
        "title": title,
        "kind": "flexible",
        "category": "homework",
        "assignment_id": "poster",
        "duration_min": 90,
        "days": [0, 1, 2, 3, 4],
    }
    rail = Rail(a_hand())
    rail.set_look(None, resolved_palette("system", False, None))
    rail.resize(RAIL_PX, 700)
    week = build_week("2026-09-21", [poster], {"poster": {"id": "poster", "due": "2026-09-25"}})
    rail.set_week(week, 3, 900, {})
    rail.show()
    qapp.processEvents()
    chip = rail.chips()[0]
    assert rail.width() == RAIL_PX, "a long title widened the rail"
    lines = chip.title_lines()
    assert len(lines) <= 2 and chip.shown_title() != title
    assert lines[-1].endswith("…"), lines
    assert chip.length == "1 h 30 min"
    assert chip.accessibleName() == f"{title} · 1 h 30 min"
    assert title in chip.toolTip()
    chip.setFixedWidth(900)
    qapp.processEvents()
    assert chip.shown_title() == title, "given room again, it says it all"


def test_rail_says_when_one_go_does_not_fit_and_offers_to_split(qapp: QApplication) -> None:
    assignment = {
        "id": "poster",
        "title": "Science poster",
        "due": "2026-09-25T23:59",
        "estimate_min": 90,
        "spread": "one",
    }
    poster = {
        "id": "poster-1",
        "title": "Science poster",
        "kind": "flexible",
        "category": "homework",
        "assignment_id": "poster",
        "duration_min": 90,
        "days": [0, 1, 2, 3, 4],
    }
    rail = Rail(a_hand())
    week = build_week("2026-09-21", [poster], {"poster": assignment})
    rail.set_week(
        week,
        0,
        16 * 60 + 30,
        {"poster": assignment},
        [{"assignment_id": "poster", "title": assignment["title"], "minutes": 90}],
        set(),
    )
    assert rail.findChild(QLabel, "railOneGoMessage") is None
    rail.set_week(
        week,
        0,
        16 * 60 + 30,
        {"poster": assignment},
        [{"assignment_id": "poster", "title": assignment["title"], "minutes": 90}],
        {"poster"},
    )
    message = rail.findChild(QLabel, "railOneGoMessage")
    assert message is not None and "doesn't fit in one go" in message.text()
    action = rail.findChild(QPushButton, "railAllowSplitting")
    assert action is not None
    assert action.accessibleName() == (
        "Science poster doesn't fit in one go before Fri 25 Sep. Allow splitting?"
    )
    selected: list[str] = []
    rail.allow_split_requested.connect(selected.append)
    action.click()
    assert selected == ["poster"]


def test_a_tray_chip_shortens_its_title_and_keeps_its_length_whole(qapp: QApplication) -> None:
    """The length is the number the chip is for, so the title gives way first: "Science pos… ·
    1 h 30 min", not "Science poster · 1 h …". With no room for a letter of the title beside the
    length, the words shorten from their end as before."""
    row = QWidget()
    line = QHBoxLayout(row)
    line.setContentsMargins(0, 0, 0, 0)
    chip = TrayChip(a_hand(), Waiting("poster", "Science poster", "homework", 90, "poster", "2026-09-25", ""))
    line.addWidget(chip)
    line.addStretch(1)
    row.show()
    qapp.processEvents()
    assert chip.text() == "Science poster · 1 h 30 min"
    fonts = chip.fontMetrics()
    # A plain button's own width beside its words: the chip's padding and frame.
    chrome = QPushButton.sizeHint(chip).width() - fonts.horizontalAdvance(chip.text())
    chip.setFixedWidth(chrome + fonts.horizontalAdvance("Science pos… · 1 h 30 min") + 1)
    qapp.processEvents()
    assert chip.text() == "Science pos… · 1 h 30 min"
    chip.setFixedWidth(chrome + fonts.horizontalAdvance(" · 1 h 30 min"))
    qapp.processEvents()
    assert chip.text().startswith("S") and chip.text().endswith("…") and "1 h 30 min" not in chip.text()


def test_a_tray_chip_in_a_row_says_it_all_again_once_the_row_has_room(qapp: QApplication) -> None:
    """The Week's tray is a row. A chip shortened while the window was narrow asks for its whole words
    again, so a wider window shows them."""
    title = "Science poster on the water cycle"
    whole = f"{title} · 1 h 30 min"
    row = QWidget()
    line = QHBoxLayout(row)
    chip = TrayChip(
        a_hand(),
        Waiting("poster", title, "homework", 90, "poster", "2026-09-25", ""),
    )
    line.addWidget(chip)
    line.addStretch(1)
    row.setFixedWidth(160)
    row.show()
    qapp.processEvents()
    assert chip.text().endswith("… · 1 h 30 min"), chip.text()
    row.setFixedWidth(700)
    qapp.processEvents()
    assert chip.text() == whole
