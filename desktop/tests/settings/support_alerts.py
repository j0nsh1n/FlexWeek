"""What the tests of the Alerts page and its pictures share: the page opened on its own."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.settings import SettingsPage
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free

ALERTS = 3
WEEKDAYS = [0, 1, 2, 3, 4]


def settings_page(qapp: QApplication, parent: QWidget | None = None, **preferences: Any) -> SettingsPage:
    """Settings on the Alerts page, shown, with reminders on and no alarms unless given."""
    dialog = SettingsPage(parent, {"reminders_enabled": True, "alarms": [], **preferences}, {}, {})
    dialog.show()
    dialog.nav.setCurrentRow(ALERTS)
    wait_until(qapp, lambda: dialog.stack.currentIndex() == ALERTS and page(dialog).isVisible())
    return dialog


def page(dialog: SettingsPage) -> QWidget:
    return dialog.stack.widget(ALERTS).widget()


def top(widget: QWidget, dialog: SettingsPage) -> int:
    return widget.mapTo(page(dialog), widget.rect().topLeft()).y()


@pytest.fixture()
def pages(qapp: QApplication) -> Iterator[Callable[..., SettingsPage]]:
    """Opens Settings on Alerts; every page is closed and freed when the test ends."""
    made: list[SettingsPage] = []

    def make(parent: QWidget | None = None, **preferences: Any) -> SettingsPage:
        dialog = settings_page(qapp, parent, **preferences)
        made.append(dialog)
        return dialog

    yield make
    for dialog in reversed(made):
        dialog.close()
        free(dialog)
