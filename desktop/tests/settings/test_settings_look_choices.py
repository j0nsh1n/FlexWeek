"""Choice cards share out into full rows (card_columns), as Setup's design cards are laid out."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.widgets import card_columns
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp, still  # noqa: F401

# ruff: noqa: F811

def test_design_cards_fill_their_rows(qapp: QApplication) -> None:
    six = 6
    assert card_columns(six, 3 * 240, 228, 12) == 3, "two full rows of three"
    assert card_columns(six, 2 * 240, 228, 12) == 2, "three full rows of two"
    assert card_columns(six, 4 * 240, 228, 12) == 3, "four fit but would leave two alone"
    assert card_columns(2, 2 * 240, 228, 12) == 2, "Day screen's two sit side by side"
    assert card_columns(5, 4 * 240, 228, 12) == 3, "five, when nothing divides, share out as 3 and 2"
    assert card_columns(6, 100, 228, 12) == 1, "a window narrower than a card gets one column"
    assert card_columns(1, 1000, 228, 12) == 1
