"""The tray chip every design's Not placed yet is made of."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from collections.abc import Iterator

from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionButton, QWidget

from desktop.native.hours.chips import TrayChip
from desktop.native.hours.hand import Hand
from desktop.native.hours.rail import PAD, RAIL_PX, RailChip
from desktop.native.weekmodel import Waiting
from desktop.native.widgets import fit_buttons


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-tray-chip-test"])


def test_a_chip_shortens_its_words_again_when_a_new_look_makes_them_larger(qapp: QApplication) -> None:
    """A new look can make the words larger without changing the chip's width, and at High contrast's
    large text they ran off its edge. The title gives way first; the length stays whole."""
    host = QWidget()
    host.setStyleSheet("QPushButton { font-size: 11pt; padding: 4px 8px; }")
    waiting = Waiting("poster", "Science poster for the fair", "assignments", 90, "poster", None, "")
    chip = TrayChip(Hand(lambda *_args: None, host), waiting, host)
    host.show()
    qapp.processEvents()
    chip.setFixedWidth(chip.sizeHint().width())
    qapp.processEvents()
    assert chip.text() == "Science poster for the fair · 1 h 30 min"
    host.setStyleSheet("QPushButton { font-size: 16pt; padding: 4px 8px; }")
    qapp.processEvents()
    option = QStyleOptionButton()
    chip.initStyleOption(option)
    room = chip.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, chip).width()
    assert chip.fontMetrics().horizontalAdvance(chip.text()) <= room, chip.text()
    assert chip.text().endswith("… · 1 h 30 min"), chip.text()


def test_fit_buttons_does_not_pin_a_rail_chip_to_its_whole_title(qapp: QApplication) -> None:
    """Sheets keep their words by raising a button's minimum width after a look change. A rail chip
    wraps its title inside the rail, so that pass must not pin it to the whole title — High contrast
    then drew 'Science poster for the fair' past the rail's edge."""
    host = QWidget()
    host.setStyleSheet("QPushButton { font-size: 16pt; }")
    waiting = Waiting("poster", "Science poster for the fair", "assignments", 90, "poster", None, "")
    chip = RailChip(Hand(lambda *_args: None, host), waiting, host)
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
