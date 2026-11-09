"""Saved preferences come back from the server as they were sent: theme pack, reminders and timer lengths."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_preferences_round_trip_keeps_theme_pack_and_reminders(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(
        {
            "theme_pack": "nocturne",
            "reminders_enabled": True,
            "reminder_lead_min": 10,
            "timer_work_min": 15,
        }
    )
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and session.preferences is not None
            and session.preferences.get("theme_pack") == "nocturne"
        ),
    )
    assert session.preferences["theme"] == "nocturne"
    assert session.preferences["reminders_enabled"] is True
    assert session.preferences["reminder_lead_min"] == 10
    assert session.preferences["timer_work_min"] == 15
