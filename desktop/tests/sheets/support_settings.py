"""A Settings page built on its own, as the Settings tests in this folder need it."""

from __future__ import annotations

from typing import Any

from desktop.native.settings import SettingsPage


def prefs_dialog(**extra: Any) -> SettingsPage:
    preferences = {"alert_volume": 80, "reminder_sound": True, "alarms": [], **extra}
    return SettingsPage(None, preferences, {}, {})
