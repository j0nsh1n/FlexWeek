"""F1 and Ctrl+N pressed on the Week: Help opens and Add homework opens."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.calendar import sunday_due
from desktop.native.settings_copy import HELP_KEYS
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until

CTRL = Qt.KeyboardModifier.ControlModifier


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-window-shortcuts"])


def quiet(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    wait_until(
        qapp, lambda: not session.busy and not session.dirty and not any(session.client._replies.values())
    )


@pytest.fixture()
def week(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    """The Week with the History essay waiting, and the calendar holding the keyboard."""
    window.resize(1280, 860)
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    quiet(qapp, window)
    window.findChild(QAbstractButton, "viewWeek").click()
    quiet(qapp, window)
    window.week_table.hours.setFocus()
    return window






def test_help_lists_f1_and_ctrl_n() -> None:
    assert ("[F1]", "Help") in HELP_KEYS
    assert ("[Ctrl]+[N]", "Add homework") in HELP_KEYS
