"""Opening Settings and saving from it: the page is built once and ahead of time, a new account never
sees the last one's choices, the footer says one thing however a save goes, and a preference that
failed to save is sent again when Settings close."""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QLabel

import desktop.native.motion as motion
from desktop.native.motion import SLIDE_NAME, apply_ui_effects
from desktop.native.settings import SettingsPage
from desktop.native.window import NativeWindow
from desktop.tests.audit_support import reconnect, refuse_all
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_settings_pages import prefs
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, still  # noqa: F401

# ruff: noqa: F811


def test_building_settings_does_not_warn_about_an_invalid_form_widget(
    qapp: QApplication, window: NativeWindow
) -> None:
    messages: list[str] = []
    previous = qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    try:
        window._discard_settings_page()
        window._open_settings()
        still(window)
    finally:
        qInstallMessageHandler(previous)
    assert window._settings is not None
    assert "QFormLayout::setRowVisible: Invalid widget" not in messages


def test_the_second_settings_open_starts_sliding_without_building_again(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closing Settings deleted the page, so every open rebuilt it before the slide could start."""
    window._motion = "normal"
    apply_ui_effects("normal")
    built = 0
    real_init = SettingsPage.__init__

    def counting_init(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        nonlocal built
        built += 1
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(SettingsPage, "__init__", counting_init)
    window._discard_settings_page()
    # The window may build Settings ahead, while it is idle; either way it is built once by the first open.
    for _ in range(60):
        qapp.processEvents()
    frames: list[float] = []
    real_run = motion._run

    def spy(owner, total, step, done):  # type: ignore[no-untyped-def]
        def seen(at: float) -> None:
            frames.append(at)
            step(at)

        real_run(owner, total, seen, done)

    monkeypatch.setattr(motion, "_run", spy)
    window._open_settings()
    still(window)
    assert built == 1
    window._settings.close_page()
    still(window)
    frames.clear()
    window._open_settings()
    qapp.processEvents()
    slides = [label for label in window._stack.findChildren(QLabel, SLIDE_NAME) if label.isVisible()]
    assert built == 1, "the page was built once while idle, not again on the second open"
    assert slides, "the slide picture is on screen at once"
    assert frames, "the first slide frame ran as the page opened"
    window._settings.close_page()
    still(window)


def test_a_new_account_never_sees_the_last_accounts_settings(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._open_settings()
    page = window._settings
    assert page is not None
    page.alarm_name.setText("Old account wake")
    page._add_alarm()
    assert page.updates()["alarms"]
    page.account_id = 0
    window._refresh_settings_page()
    fresh = window._settings
    assert fresh is not None
    assert fresh.account_id == window.session.account["id"]
    assert fresh.updates()["alarms"] == []


def test_settings_hears_the_status_once_and_never_warns_on_open(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opening Settings tried to disconnect a status line that was never connected, which PySide warns
    about on every first open. Open twice and a status still arrives once, with no warning."""
    heard: list[str] = []
    real = SettingsPage.say

    def counting(self: SettingsPage, text: str) -> None:
        heard.append(text)
        real(self, text)

    monkeypatch.setattr(SettingsPage, "say", counting)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        window._open_settings()
        still(window)
        window._settings.close_page()
        still(window)
        window._open_settings()
        still(window)
    assert not [w for w in caught if "disconnect" in str(w.message)], [str(w.message) for w in caught]
    window.session.status.emit("Saved")
    assert heard.count("Saved") == 1
    window._settings.close_page()
    still(window)


def test_settings_pictures_made_ahead_are_drawn_a_turn_at_a_time(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Settings is built ahead, off screen, after the window opens. Its design pictures take a while
    each; drawn all at once they held every key and click. Getting Settings ready draws none of them
    itself, and all of them are drawn soon after."""
    from desktop.native.layouts import dialog as dialog_module
    from desktop.native.layouts.dialog import DesignPicker

    if window._settings is None:
        window._prepare_settings_page()
    page = window._settings
    assert page is not None
    pickers = page.findChildren(DesignPicker)
    assert pickers
    drawn: list[str] = []

    class Counting(dialog_module.Previews):  # type: ignore[misc, valid-type]
        def get(self, layout_id: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            drawn.append(layout_id)
            return super().get(layout_id, *args, **kwargs)

    monkeypatch.setattr(dialog_module, "Previews", Counting)
    for picker in pickers:
        picker._waiting = list(range(len(picker.cards)))
    window._warm_settings_pictures()
    assert drawn == [], "getting Settings ready drew pictures in the same turn"
    wait_until(qapp, lambda: all(not picker._waiting for picker in pickers), 10.0)
    assert len(drawn) == sum(len(picker.cards) for picker in pickers)


def test_the_footer_says_one_thing_however_a_save_goes(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window)
    standing = "Changes are saved as you make them."
    assert dialog.save_state.text() == standing
    for routine in ("Saving preferences…", "Saved preferences.", "Saving…", "Saved.", "This week."):
        window.session.status.emit(routine)
        assert dialog.save_state.text() == standing
    window.session.status.emit("Could not reach the server.")
    assert dialog.save_state.text() == "Could not reach the server.", "what needs reading still shows"
    window.session.status.emit("Saved preferences.")
    assert dialog.save_state.text() == standing


def test_a_preference_that_failed_to_save_is_sent_again_when_settings_close(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The page took a queued request for a saved one, so after the connection came back, closing
    Settings sent nothing and the old length returned."""
    window._open_settings()
    page = window._settings
    assert page is not None
    sent = refuse_all(window, "PUT", "/api/preferences")
    page.work.setValue(45)
    wait_until(qapp, lambda: len(sent) == 1)
    assert sent[0]["timer_work_min"] == 45
    wait_until(qapp, lambda: not window.session.busy)
    reconnect(window)
    window._close_settings()
    wait_until(qapp, lambda: not window.session.busy)
    assert window.session.preferences["timer_work_min"] == 45
