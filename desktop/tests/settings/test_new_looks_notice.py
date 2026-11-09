"""The one-time look notice belongs to existing accounts on this device.

How the notice is drawn (its card, its edge, its colours reading on the card, and the week behind it
staying put) is the pictures settings.new_looks_notice and settings.ordinary_toast.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import json
from copy import deepcopy

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window as fresh_window  # noqa: F401
from desktop.tests.settings.support_new_looks_notice import NOTICE, make_legacy_account
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def test_an_account_made_before_the_designs_had_looks_sees_the_notice_once_on_its_first_planner_open(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)

    window._on_week()

    assert window.toast.isVisible()
    assert window.toast.text() == NOTICE
    assert window.toast.button.text() == "Choose a look"
    # One action and the x: "Not now" is gone, the x does what it did.
    assert not window.toast.secondary_button.isVisibleTo(window.toast)
    assert window.toast.close_button.isVisibleTo(window.toast)
    assert str(window.session.account["id"]) not in window._new_look_notice_seen
    assert window.session.preferences == preferences
    assert window._look == look
    window._on_week()
    assert window.toast.isVisible() and window.toast.text() == NOTICE


def test_a_fresh_account_does_not_see_the_notice_after_setup(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    assert fresh_window.session.preferences["setup"].get("finished_at")
    assert fresh_window.session.new_account
    fresh_window._on_week()
    assert fresh_window.toast.text() != NOTICE
    account_id = str(fresh_window.session.account["id"])
    assert account_id not in fresh_window._new_look_notice_seen
    assert account_id in fresh_window._new_look_notice_exempt
    fresh_window.session.new_account = False
    fresh_window._load_look()
    fresh_window._on_week()
    assert fresh_window.toast.text() != NOTICE


def test_esc_closes_the_notice_for_that_account_on_this_device(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    """Esc is the x, from whatever notice button holds focus."""
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = str(window.session.account["id"])
    window.toast.button.setFocus()
    qapp.processEvents()
    QTest.keyClick(window.toast.button, Qt.Key.Key_Escape)

    assert not window.toast.isVisible()
    assert account_id in window._new_look_notice_seen
    stored = json.loads(look_file().read_text())
    assert account_id in stored["new_look_notice_seen"]
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_tab_reaches_the_notice_s_button_and_its_x(qapp: QApplication, fresh_window: NativeWindow) -> None:
    window = fresh_window
    make_legacy_account(window)
    # An empty week shows its welcome, with no hours canvas for the notice's Tab chain to start from.
    window.session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 240,
            "days": [0, 1, 2, 3, 4],
        }
    )
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    window._on_week()
    canvas = next(surface for surface in window._week_surfaces() if surface.isVisible())
    canvas.setFocus()
    qapp.processEvents()
    QTest.keyClick(canvas, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is window.toast.button
    QTest.keyClick(window.toast.button, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is window.toast.close_button


def test_choose_a_look_dismisses_the_notice_and_opens_settings_at_look(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = window.session.account["id"]
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)
    layout = deepcopy(window._layout)
    window.toast.button.click()

    assert str(account_id) in window._new_look_notice_seen
    assert window._stack.currentWidget() is window._settings
    assert window._settings.nav.currentRow() == 0
    assert window._settings.nav.currentItem().text() == "Look"
    assert window.session.preferences == preferences
    assert window._look == look
    assert window._layout == layout
    stored = json.loads(look_file().read_text())
    assert str(account_id) in stored["new_look_notice_seen"]
    window._close_settings(save=False)
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_closing_the_notice_keeps_it_dismissed_on_this_device(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = str(window.session.account["id"])
    window.toast.close_button.click()

    assert not window.toast.isVisible()
    assert account_id in window._new_look_notice_seen
    stored = json.loads(look_file().read_text())
    assert account_id in stored["new_look_notice_seen"]
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_an_account_with_any_saved_design_look_does_not_get_the_notice(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    saved = json.loads(look_file().read_text())
    saved["layout"]["options"] = {"classic": {"look": "your"}}
    look_file().write_text(json.dumps(saved) + "\n")
    window._load_look()
    window._on_week()

    assert window.toast.text() != NOTICE
    assert str(window.session.account["id"]) not in window._new_look_notice_seen
