"""Month keeps the last grid it drew while the next month loads, instead of going blank."""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QAbstractButton, QApplication

    from desktop.native.window import NativeWindow
    from desktop.tests.light_app import window  # noqa: F401
    from desktop.tests.test_week_side import seeded
    from desktop.tests.waiting import wait_until
    from desktop.tests.window_support import qapp, still  # noqa: F401


def month_days(window: NativeWindow) -> list[str]:
    return [cell.iso for cell in window.month_grid.canvas.cells]


def test_week_to_month_to_the_next_month_never_shows_an_empty_grid(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    seeded(qapp, window)
    window.findChild(QAbstractButton, "viewMonth").click()
    wait_until(qapp, lambda: window.session.month_data is not None)
    still(window)
    first = month_days(window)
    assert first
    # The next month is on its way: the session has dropped the old one and asked for the new.
    window.next_nav.click()
    assert window.session.month_data is None, "the next month has not arrived yet"
    month = window.session.selected_month
    first_day = date.fromisoformat(month + "-01")
    last_day = (first_day + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    start = first_day - timedelta(days=first_day.weekday())
    end = last_day + timedelta(days=6 - last_day.weekday())
    expected = [(start + timedelta(days=index)).isoformat() for index in range((end - start).days + 1)]
    assert month_days(window) == expected
    assert month_days(window) != first, "the next month's dates are drawn while its data loads"
    assert window.month_grid.warning.text() == ""
    wait_until(qapp, lambda: window.session.month_data is not None)
    assert month_days(window) and month_days(window) != first
    assert window.month_grid.warning.text() == ""
