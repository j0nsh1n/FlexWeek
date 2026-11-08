# ruff: noqa: F811
"""Settings as a page of the window: how it opens and closes, when it saves, what it holds, and the
preferences the window obeys (drag step, alarm sound, where the app opens)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QRadioButton  # noqa: E402

from desktop.native.settings import SettingsPage  # noqa: E402
from desktop.native.version import VERSION  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    combo,
    open_settings,
    preference_puts,
    qapp,  # noqa: F401
    wait_until,
    window,  # noqa: F401
)


def test_a_settings_change_shows_before_settings_closes(qapp: QApplication, window: NativeWindow) -> None:
    """No OK: picking Bento changes the view behind Settings while it is still open, and so does an
    accent, and going back keeps both."""
    page = open_settings(window)
    pick = combo(page, "layoutMain")
    pick.setCurrentIndex(pick.findData("bento"))
    assert type(window.planner.currentWidget()).__name__ == "BentoView"
    assert window._stack.currentWidget() is page, "the change leaves Settings on screen"
    page.accent.setCurrentIndex(page.accent.findData("sea"))
    assert (window.session.preferences or {}).get("accent") == "sea"
    page.close_page()
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window._layout["main"] == "bento"


def test_settings_is_a_page_the_gear_opens_and_done_or_esc_closes(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Settings fills the window in place of the week, and the week's keys leave it alone."""
    window.findChild(QPushButton, "settingsGear").click()
    page = window._settings
    assert isinstance(page, SettingsPage) and window._stack.currentWidget() is page
    view = window.session.planner_view
    QTest.keyClick(page.nav, Qt.Key.Key_M)
    assert window.session.planner_view == view and window._stack.currentWidget() is page
    page.done.click()
    assert window._stack.currentWidget().objectName() == "weekPage"
    page = open_settings(window)
    QTest.keyClick(page.nav, Qt.Key.Key_Escape)
    assert window._stack.currentWidget().objectName() == "weekPage"


def test_the_gear_opens_settings(qapp: QApplication, window: NativeWindow) -> None:
    gear = window.findChild(QPushButton, "settingsGear")
    assert gear is not None
    assert gear.text() == "" and not gear.icon().isNull()
    assert gear.toolTip() == "Settings"
    assert gear.accessibleName() == "Settings"
    click(window, "settingsGear")
    assert window._stack.currentWidget().objectName() == "settingsPage"
    window._settings.close_page()


def test_settings_saves_once_after_a_burst_and_closing_saves_it_at_once(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Typing 2, 25, 45 is one save of 45, sent as Settings closes rather than lost with it."""
    sent = preference_puts(window)
    page = open_settings(window)
    for value in (2, 25, 45):
        page.work.setValue(value)
    page.close_page()
    assert [payload["timer_work_min"] for payload in sent] == [45]
    wait_until(qapp, lambda: not window.session.busy)
    # What the server sent back, not what the page showed: the timers are not shown ahead of the save.
    assert (window.session.preferences or {})["timer_work_min"] == 45


def test_the_drag_step_is_chosen_in_settings_kept_by_the_account_and_given_to_the_hand(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Five minutes until the student says otherwise. Fifteen, picked in Settings, moves the hand at
    once, is saved with the account and read back from it; five again is the default once more."""
    assert window.hand.step == 5

    def stored() -> dict:
        got: dict = {}
        window.session.client.request(
            "GET", "/api/preferences", None, got.update, lambda error: got.update(error=error)
        )
        wait_until(qapp, lambda: bool(got))
        return got

    for choice in (15, 5):
        page = open_settings(window)
        page.findChild(QRadioButton, f"prefDragStep-{choice}").click()
        assert window.hand.step == choice, "applied while Settings is open"
        page.close_page()
        wait_until(qapp, lambda: not window.session.busy)
        assert stored().get("drag_step_min", 5) == choice
        assert window.hand.step == choice


def test_a_pause_saves_without_closing_settings(qapp: QApplication, window: NativeWindow) -> None:
    sent = preference_puts(window)
    page = open_settings(window)
    page.volume.setValue(35)
    wait_until(qapp, lambda: bool(sent))
    assert [payload["alert_volume"] for payload in sent] == [35]
    page.close_page()
    # Nothing changed after that save, so closing sends nothing more.
    assert [payload["alert_volume"] for payload in sent] == [35]


def test_settings_holds_account_availability_and_updates(qapp: QApplication, window: NativeWindow) -> None:
    prefs = window.session.preferences or {}
    dialog = SettingsPage(window, prefs, window._look, window.session.reminder_limits)
    assert dialog.findChild(QPushButton, "prefsAccount") is not None
    assert dialog.findChild(QPushButton, "prefsAvailability") is not None
    assert dialog.findChild(QLabel, "prefsVersion").text() == f"FlexWeek {VERSION}"
    assert dialog.findChild(QPushButton, "prefsCheckUpdates") is not None
    asked: list[str] = []
    dialog.account_requested.connect(lambda: asked.append("account"))
    dialog.availability_requested.connect(lambda: asked.append("availability"))
    dialog.updates_requested.connect(lambda: asked.append("updates"))
    dialog.findChild(QPushButton, "prefsAccount").click()
    dialog.findChild(QPushButton, "prefsAvailability").click()
    dialog.findChild(QPushButton, "prefsCheckUpdates").click()
    assert asked == ["account", "availability", "updates"]
    dialog.close()


def test_settings_picks_the_alarm_sound_and_new_alarms_start_with_it(qapp: QApplication) -> None:
    dialog = SettingsPage(None, {"alarm_tone": "low"}, {}, {}, None)
    tone = combo(dialog, "prefAlarmTone")
    assert tone.currentData() == "low"
    assert combo(dialog, "alarmSound").currentData() == "low"
    tone.setCurrentIndex(tone.findData("glass"))
    assert combo(dialog, "alarmSound").currentData() == "glass"
    assert dialog.updates()["alarm_tone"] == "glass"
    dialog.show()
    # On the Alerts page, which is not the page on screen, so the row's own state is what counts.
    assert dialog.tone_note.isHidden() is True
    tone.setCurrentIndex(tone.findData("spotify"))
    assert dialog.tone_note.isHidden() is False
    played: list[str] = []
    tone.setCurrentIndex(tone.findData("bright"))
    dialog._tone_bell.once = lambda name, _volume: played.append(name) or True
    dialog.play_tone.click()
    assert played == ["bright"]
    dialog.close()


def test_open_on_day_is_honoured_instead_of_always_coming_up_on_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The setting could be saved from the desktop but only the web read it."""
    window._day_mode = False
    window._opened_on_preference = False
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "day"}
    window._on_week()
    qapp.processEvents()
    assert window._day_mode is True


def test_open_on_is_a_starting_point_not_a_lock(qapp: QApplication, window: NativeWindow) -> None:
    """Every week refresh runs through the same path, so applying it more than once would drag the
    student back to the day screen whenever the week reloaded."""
    window._day_mode = False
    window._opened_on_preference = False
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "day"}
    window._on_week()
    qapp.processEvents()
    window._leave_day()
    qapp.processEvents()
    assert window._day_mode is False
    window._on_week()
    qapp.processEvents()
    assert window._day_mode is False
