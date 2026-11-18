# ruff: noqa: F811
"""A failed save in Material 3: the snackbar and the top bar both offer Retry save, and Ctrl+S still sends
the waiting changes."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import fail_once
from desktop.tests.material_support import pump, qml, show_material
from desktop.tests.sheets.support_material_sheets import click
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def _failed_save(qapp: QApplication, window: NativeWindow) -> object:
    root = show_material(qapp, window)
    session = window.session
    session.add_homework(
        {
            "id": "retry-me",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    fail_once(session, "POST", "/api/changes")
    session.save()
    wait_until(qapp, lambda: not session.busy)
    pump(qapp)
    assert session.pending_save is not None, "the save did not fail"
    return root


def test_a_failed_save_offers_retry_in_the_snackbar_and_the_top_bar(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _failed_save(qapp, window)
    bridge = window._material_page.bridge
    assert str(bridge.property("snackAction")) == "RETRY"
    assert "Not saved" in str(bridge.property("snackText"))
    button = qml(root, "materialRetrySave")
    assert button.property("visible") and button.property("enabled")
    assert str(button.property("text")) == "Retry save"


def _count_retries(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    real = window.session.retry_save
    monkeypatch.setattr(window.session, "retry_save", lambda: (calls.append(1), real())[1])
    return calls


def test_the_retry_button_sends_the_waiting_changes_and_goes_away(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _failed_save(qapp, window)
    calls = _count_retries(window, monkeypatch)
    click(window, qml(root, "materialRetrySave"))
    assert calls == [1], "the button did not ask the session to retry"
    wait_until(qapp, lambda: window.session.pending_save is None and not window.session.busy)
    pump(qapp)
    assert window.session.dirty is False
    assert not qml(root, "materialRetrySave").property("visible")
    assert str(window._material_page.bridge.property("snackText")) == ""


def test_the_snackbar_retry_sends_the_waiting_changes(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _failed_save(qapp, window)
    calls = _count_retries(window, monkeypatch)
    qml(root, "materialSnackbar").actionClicked.emit()
    assert calls == [1]
    wait_until(qapp, lambda: window.session.pending_save is None and not window.session.busy)


def test_ctrl_s_still_sends_the_waiting_changes(qapp: QApplication, window: NativeWindow) -> None:
    _failed_save(qapp, window)
    QTest.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    wait_until(qapp, lambda: window.session.pending_save is None and not window.session.busy)


def test_no_retry_is_shown_when_nothing_is_waiting(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    assert window.session.pending_save is None
    assert not qml(root, "materialRetrySave").property("visible")
