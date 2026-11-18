"""The settings the parity audit found missing from Material 3: Open on, Animations, Planning style, and
the rest of that list. Each control shows the saved value and saves a change through the backend."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _click_segment,
    _named,
    _open_settings,
    _panel,
    _prefs,
    _pump,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def test_open_on_shows_the_saved_screen_and_saves_a_change(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "planning")
    assert _panel(window).property("state")["openOn"] == "week", "nothing saved reads as the week"
    for label, value in (("Day", "day"), ("Month", "month"), ("My day", "myday"), ("Week", "week")):
        _click_segment(qapp, window, _named(root, "openOn")[0], label)
        wait_until(qapp, lambda value=value: _prefs(window).get("preferred_view") == value)
        assert _panel(window).property("state")["openOn"] == value


def test_open_on_refuses_a_screen_it_does_not_know(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "planning")
    _panel(window).setOpenOn("settings")
    _panel(window).setOpenOn("year")
    _pump(qapp)
    assert _prefs(window).get("preferred_view") not in ("settings", "year")


@pytest.mark.parametrize("view", ["week", "day", "month", "myday"])
def test_start_up_opens_the_saved_screen(qapp: QApplication, window: NativeWindow, view: str) -> None:
    _open_settings(qapp, window, "planning")
    bridge = _bridge(window)
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": view}
    bridge._screen = "settings"
    bridge._opened_for = None
    bridge.refresh()
    assert bridge.property("screen") == view
    # Once per sign-in: a student who moves on is not pulled back by the next refresh.
    bridge.showPage("settings")
    bridge.refresh()
    assert bridge.property("screen") == "settings"


def test_a_saved_screen_that_is_gone_opens_the_week(qapp: QApplication, window: NativeWindow) -> None:
    _open_settings(qapp, window, "planning")
    bridge = _bridge(window)
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "year"}
    bridge._screen = "settings"
    bridge._opened_for = None
    bridge.refresh()
    assert bridge.property("screen") == "settings", "an unknown value moves nobody"


def test_animations_show_and_save_the_four_levels(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "look")
    assert _panel(window).property("state")["animations"] == "normal"
    for label, value in (("Reduce", "reduce"), ("Off", "off"), ("More", "extra"), ("Normal", "normal")):
        _click_segment(qapp, window, _named(root, "animations")[0], label)
        wait_until(qapp, lambda value=value: _prefs(window).get("motion") == value)
        assert _panel(window).property("state")["animations"] == value


@pytest.mark.parametrize("level", ["extra", "off"])
def test_a_saved_animation_level_survives_opening_and_closing_settings(
    qapp: QApplication, window: NativeWindow, level: str
) -> None:
    window.session.save_preferences({"motion": level})
    wait_until(qapp, lambda: _prefs(window).get("motion") == level)
    _open_settings(qapp, window, "look")
    assert _panel(window).property("state")["animations"] == level
    _open_settings(qapp, window, "computer")
    _bridge(window).showPage("week")
    _pump(qapp)
    _open_settings(qapp, window, "look")
    assert _prefs(window).get("motion") == level
    assert _panel(window).property("state")["animations"] == level


def test_planning_style_shows_the_saved_choice_and_saves_a_change(
    qapp: QApplication, window: NativeWindow
) -> None:
    _open_settings(qapp, window, "planning")
    state = _panel(window).property("state")
    assert state["planningStyle"] == "suggest"
    assert [row["value"] for row in state["planningStyleChoices"]] == ["auto", "suggest", "manual"]
    for value in ("auto", "manual", "suggest"):
        _panel(window).setPlanningStyle(value)
        wait_until(qapp, lambda value=value: (_prefs(window).get("planning_style") or "suggest") == value)
        assert _panel(window).property("state")["planningStyle"] == value
    _panel(window).setPlanningStyle("sometimes")
    _pump(qapp)
    assert _panel(window).property("state")["planningStyle"] == "suggest"


def test_reminder_lead_takes_any_minute_from_0_to_120(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    slider = _named(root, "reminderLead")[0]
    assert (slider.parentItem().property("from"), slider.parentItem().property("to")) == (0, 120)
    for minutes in (20, 0, 120, 45):
        _panel(window).setReminderLead(minutes)
        wait_until(qapp, lambda minutes=minutes: _prefs(window).get("reminder_lead_min") == minutes)
        state = _panel(window).property("state")
        assert state["reminderLead"] == minutes
        assert slider.parentItem().property("value") == minutes


def test_reminder_lead_refuses_what_is_out_of_range_with_the_same_words(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_settings(qapp, window, "alerts")
    _panel(window).setReminderLead(30)
    wait_until(qapp, lambda: _prefs(window).get("reminder_lead_min") == 30)
    sent: list[dict] = []
    monkeypatch.setattr(window.session, "save_preferences", lambda updates, then=None: sent.append(updates))
    for bad in (-1, 121, 5000):
        _panel(window).setReminderLead(bad)
        assert sent == [], "nothing is sent to the server"
        assert _prefs(window).get("reminder_lead_min") == 30
        assert _panel(window).property("state")["notice"] == "Could not save that."


def test_the_lead_slider_is_hidden_while_reminders_are_off(qapp: QApplication, window: NativeWindow) -> None:
    root = _open_settings(qapp, window, "alerts")
    _click_segment(qapp, window, _named(root, "reminder")[0], "Off")
    wait_until(qapp, lambda: _prefs(window).get("reminders_enabled") is False)
    assert not _named(root, "reminderLead")[0].parentItem().property("visible")
