"""The overdue card above the week. How its two buttons are laid out (whole labels, under the words when
the card is narrow) is a picture: screens_sheets_h7.py."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_overdue_card import DESIGNS, show_overdue_card
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize("main", DESIGNS)
def test_a_homework_left_overdue_shows_the_card_with_its_two_buttons_in_every_design(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    main: str,
) -> None:
    show_overdue_card(window, main)
    assert window.left_chip.isVisible(), "the overdue card is not showing"
    for name in ("leftPlan", "leftDone"):
        button = window.findChild(QPushButton, name)
        assert button is not None and button.isVisible() and button.isEnabled(), (main, name)
        assert button.text(), (main, name)
