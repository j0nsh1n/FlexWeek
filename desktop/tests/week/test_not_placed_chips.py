"""The chips every design's Not placed yet is made of: a long title gives way before the length does when a
new look makes the words larger, and a rail chip is not pinned to its whole title. That the words then fit
inside the chip is a picture (desktop/tests/pictures/_week_g14.py, week.not_placed_chips)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.hours.chips import TrayChip
from desktop.native.hours.hand import Hand
from desktop.native.hours.rail import PAD, RAIL_PX, RailChip
from desktop.native.weekmodel import Waiting
from desktop.native.widgets import fit_buttons
from desktop.tests.waiting import wait_until

WHOLE = "Science poster for the fair · 1 h 30 min"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-not-placed-chips"])


def poster() -> Waiting:
    return Waiting("poster", "Science poster for the fair", "assignments", 90, "poster", None, "")


def test_a_chip_shortens_its_title_again_when_a_new_look_makes_the_words_larger(qapp: QApplication) -> None:
    """A new look can make the words larger without changing the chip's width, and at High contrast's
    large text they ran off its edge. The title gives way first; the length stays whole."""
    host = QWidget()
    host.setStyleSheet("QPushButton { font-size: 11pt; padding: 4px 8px; }")
    chip = TrayChip(Hand(lambda *_args: None, host), poster(), host)
    host.show()
    qapp.processEvents()
    chip.setFixedWidth(chip.sizeHint().width())
    qapp.processEvents()
    assert chip.text() == WHOLE
    host.setStyleSheet("QPushButton { font-size: 16pt; padding: 4px 8px; }")
    wait_until(qapp, lambda: chip.text() != WHOLE, 2.0, what=lambda: f"the chip still said {chip.text()!r}")
    assert chip.text().endswith("… · 1 h 30 min"), chip.text()
    assert chip.text().startswith("Science"), chip.text()


def test_fit_buttons_does_not_pin_a_rail_chip_to_its_whole_title(qapp: QApplication) -> None:
    """Sheets keep their words by raising a button's minimum width after a look change. A rail chip wraps
    its title inside the rail, so that pass must not pin it to the whole title: High contrast then drew
    'Science poster for the fair' past the rail's edge."""
    host = QWidget()
    host.setStyleSheet("QPushButton { font-size: 16pt; }")
    chip = RailChip(Hand(lambda *_args: None, host), poster(), host)
    cap = RAIL_PX - 2 * PAD
    chip.setMaximumWidth(cap)
    chip.setMinimumWidth(0)
    host.show()
    qapp.processEvents()
    need = chip.fontMetrics().horizontalAdvance(chip.text())
    assert need > cap, "the large title must outrun the rail or this does not watch the bug"
    fit_buttons(host)
    qapp.processEvents()
    assert chip.minimumWidth() <= cap, chip.minimumWidth()
