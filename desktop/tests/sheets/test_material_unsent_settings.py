# ruff: noqa: F811
"""Settings and Material 3 in one window: a Settings change the account refused to save is still on the
page after switching between Material and the Widgets styles and after Sign out, and Settings stays open
(or comes back) around a refresh and Done.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QSpinBox, QWidget  # noqa: E402

from desktop.native.remind import reminder_lead_min  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import pump, show_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402

SIGN_OUT_REFUSED = (
    "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. "
    "Choose Retry save, then sign out again."
)


def _open_widgets_settings(window: NativeWindow) -> QWidget:
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._open_settings()
    page = window._settings
    assert page is not None
    return page


def _hold_the_page_still(page: QWidget) -> None:
    """The page's timers would send the change on their own; the test wants it unsent."""
    for timer in page.findChildren(QTimer):
        timer.stop()


def _stop_leaving(window: NativeWindow) -> None:
    leaving = window._leaving
    if leaving is not None:
        leaving.stop()
        leaving.deleteLater()
        window._leaving = None


def _accept_sign_out() -> None:
    """Press Sign out on the sheet that is about to open. Esc and Cancel leave the account signed in."""
    tries = [0]

    def press() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None and hasattr(sheet, "buttons"):
            sheet.buttons["yes"].click()
        elif tries[0] < 200:
            tries[0] += 1
            QTimer.singleShot(20, press)

    QTimer.singleShot(0, press)


def test_an_unsent_settings_change_survives_the_swap(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    page = _open_widgets_settings(window)
    clock = page.findChild(QWidget, "prefClock")
    # The change is whatever the open page is showing, not the account dict. A week refresh can
    # have built this page before a later test wrote the account's clock.
    wanted = not bool(clock.currentData())
    window.session.save_preferences = lambda _wanted, _done: False

    clock.setCurrentIndex(0 if wanted else 1)
    _hold_the_page_still(page)
    page.findChild(QPushButton, "chooseMaterial").click()
    pump(qapp)

    assert window._stack.currentWidget().objectName() == "materialPage"
    assert page.updates()["clock_24h"] is wanted
    assert window._settings_unsent() is True
    window._use_widgets_styles()
    pump(qapp)
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window._settings is page
    assert page.updates()["clock_24h"] is wanted
    window._open_settings()
    assert window._settings_unsent() is True
    assert bool(page.findChild(QWidget, "prefClock").currentData()) is wanted


def test_an_unsent_reminder_lead_survives_the_swap_back(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    """A refused preference save must still be on the lead control after Material and after reopening."""
    window = material_window
    page = _open_widgets_settings(window)
    lead = page.findChild(QSpinBox, "prefLead")
    assert lead.value() == 5
    assert lead.value() == reminder_lead_min(window.session.preferences)
    saved: list[object] = []

    def refuse(wanted: dict, _done: object) -> bool:
        saved.append(wanted.get("reminder_lead_min"))
        return False

    window.session.save_preferences = refuse
    try:
        lead.setValue(17)
        _hold_the_page_still(page)
        page.findChild(QPushButton, "chooseMaterial").click()
        pump(qapp)
        assert window._stack.currentWidget().objectName() == "materialPage"
        window._use_widgets_styles()
        pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window._settings_unsent() is True
        assert lead.value() == 17
        assert window._save_before_leaving(lambda: None) is False
        wait_until(qapp, lambda: 17 in saved, what="the refused save to be offered the lead")
        window._open_settings()
        pump(qapp)
        assert window._stack.currentWidget().objectName() == "settingsPage"
        assert page.findChild(QSpinBox, "prefLead").value() == 17
    finally:
        _stop_leaving(window)


def test_sign_out_keeps_an_unsent_settings_change_on_both_surfaces(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    """A refused preference save is still the lead after Sign out is confirmed.

    Material's More and the Widgets button both reach the same sign-out. Signing out
    used to drop the draft and leave the saved lead at 5.
    """
    window = material_window
    page = _open_widgets_settings(window)
    lead = page.findChild(QSpinBox, "prefLead")
    assert lead.value() == 5
    assert lead.value() == reminder_lead_min(window.session.preferences)
    offered: list[object] = []
    logged_out: list[int] = []
    original_logout = window.session.logout

    def refuse(wanted: dict, _done: object) -> bool:
        offered.append(wanted.get("reminder_lead_min"))
        return False

    def watch_logout() -> None:
        logged_out.append(reminder_lead_min(window.session.preferences))
        original_logout()

    window.session.save_preferences = refuse
    window.session.logout = watch_logout
    try:
        lead.setValue(17)
        _hold_the_page_still(page)
        root = show_material(qapp, window)
        assert window._settings_unsent() is True
        window._material_page.bridge.openMore()
        pump(qapp)
        assert window._material_page.bridge.sheets.moreOpen is True
        _accept_sign_out()
        window._material_page.bridge.sheets.moreAction("signOut")
        wait_until(
            qapp,
            lambda: window.session.message == SIGN_OUT_REFUSED,
            what=lambda: f"the window said {window.session.message!r}",
        )
        assert logged_out == []
        assert window.session.account is not None
        assert reminder_lead_min(window.session.preferences) == 5
        assert lead.value() == 17
        assert 17 in offered
        assert root.objectName() == "materialShell"

        offered.clear()
        window._use_widgets_styles()
        pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window._settings_unsent() is True
        _accept_sign_out()
        window.findChild(QPushButton, "signOut").click()
        wait_until(qapp, lambda: 17 in offered, what="the refused save to be offered the lead again")
        pump(qapp)
        assert logged_out == []
        assert window.session.account is not None
        assert reminder_lead_min(window.session.preferences) == 5
        assert lead.value() == 17
        assert "sign out again." in window.session.message
    finally:
        _stop_leaving(window)
        sheet = QApplication.activeModalWidget()
        if isinstance(sheet, QDialog):
            sheet.reject()


def test_a_refresh_with_settings_open_keeps_settings(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    trace = {"placed": [], "kept": "settings"}
    window.session.trace = trace
    window.session._fresh_plan = True
    show_material(qapp, window)
    window._open_settings()
    assert window._stack.currentWidget().objectName() == "settingsPage"

    window.session.week_changed.emit()
    pump(qapp)

    assert window._stack.currentWidget().objectName() == "settingsPage"
    assert window.plan_review.isHidden()
    assert window.session._fresh_plan is True


def test_closing_settings_returns_to_material(qapp: QApplication, material_window: NativeWindow) -> None:
    show_material(qapp, material_window)
    material_window._open_settings()

    material_window._settings.findChild(QPushButton, "settingsDone").click()
    pump(qapp)

    assert material_window._stack.currentWidget().objectName() == "materialPage"
