# ruff: noqa: F811
"""The dialog an alarm rings in. How big it is and how its buttons look is the picture
sheets.alarm_ringing (desktop/tests/pictures/_sheets_g05.py)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.remind import ALARM_SNOOZE_MIN  # noqa: E402
from desktop.native.settings import AlarmRingDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-alarm-ring-dialog-test"])


def test_the_snooze_button_says_how_long_it_snoozes_for(qapp: QApplication) -> None:
    dialog = AlarmRingDialog(None, {"name": "Wake up", "time": "06:45"}, "")
    button = dialog.findChild(QPushButton, "alarmSnooze")
    assert button is not None and str(ALARM_SNOOZE_MIN) in button.text()
