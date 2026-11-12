"""The line under Start and End in the fixed-time editor says what the times mean, in time for the student
to act: a time that has already passed is refused in words, End's move is previewed while Start is
half typed, and a fresh sheet does not announce a move nobody made.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.widgets import BlockDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_clock_typing import (
    press,
    show_and_focus,
    tab_into,
    twelve_hour_clock,  # noqa: F401
    type_text,
)
from desktop.tests.sheets.support_fixed_time import go_when
from desktop.tests.window_support import free, host, qapp  # noqa: F401


@pytest.mark.usefixtures("twelve_hour_clock")
def test_a_new_fixed_block_at_a_past_time_is_accepted(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """A fixed time may start on a day that is over or earlier today; no past-time line appears."""
    CLOCK.set(datetime.fromisoformat(window.session.week_start) + timedelta(days=3, hours=16, minutes=40))
    for day, start in ((1, "09:00"), (3, "09:00")):
        dialog = BlockDialog(window, day=day, start=start)
        dialog.title.setText("Early club")
        go_when(dialog)
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted, (day, start)
        assert "That time has passed" not in dialog.duration_line.text()
        assert (dialog.block()["days"], dialog.block()["start"]) == ([day], start)
        dialog.close()


@pytest.mark.usefixtures("twelve_hour_clock")
def test_the_duration_line_follows_start_before_it_settles(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    """While Start is half-typed, Duration previews where End will move."""
    dialog = BlockDialog(host, day=3, start="16:00", duration_min=120)
    show_and_focus(qapp, dialog)
    dialog.title.setText("Club")
    go_when(dialog)
    tab_into(dialog.start)
    type_text(dialog.start, "4:30 PM")
    assert dialog.duration_line.text() == "End will move to 6:30 PM (2 h)"
    dialog.close()
    hand = BlockDialog(host, day=3, start="16:30", duration_min=90)
    show_and_focus(qapp, hand)
    hand.title.setText("Hand end")
    go_when(hand)
    tab_into(hand.end)
    type_text(hand.end, "6:00 PM")
    press(hand.end, Qt.Key.Key_Tab)
    tab_into(hand.start)
    type_text(hand.start, "4:30 PM")
    assert hand.duration_line.text() == "1 h 30 min"
    hand.close()


def test_add_fixed_time_does_not_say_end_moved_before_start_changes(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    """Tab out of Start on a fresh sheet must not announce a move."""
    dialog = BlockDialog(host, day=3, start="16:00", duration_min=60)
    dialog.title.setText("Club")
    go_when(dialog)
    dialog.start.setFocus()
    QTest.keyClick(dialog.start, Qt.Key.Key_Tab)
    assert "End moved" not in dialog.duration_line.text()
    dialog.close()
    free(dialog)
