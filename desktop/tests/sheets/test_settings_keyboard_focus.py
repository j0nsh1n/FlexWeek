"""Material's Settings and the Manage account sheet with the keyboard: a row reached with Tab scrolls into
view with its ring, Esc closes Manage account and Advanced settings, and the keyboard goes back to the row
that opened them."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from desktop.native.settings import AccountDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, qml
from desktop.tests.sheets.support_settings_keys import open_settings, panel
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def _find_qml_child(parent, name: str):
    for child in parent.childItems():
        if child.objectName() == name:
            return child
        found = _find_qml_child(child, name)
        if found is not None:
            return found
    return None


def test_advanced_settings_row_shows_the_ring_and_scrolls_into_view_on_tab(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_settings(qapp, window, "look")
    scroller = qml(root, "lookSection")
    advanced_rows = named(root, "openAdvanced")
    assert advanced_rows, "openAdvanced row not found"
    advanced_row = advanced_rows[0]

    scroller.setProperty("contentY", 0.0)
    pump(qapp)

    advanced_row.forceActiveFocus()
    pump(qapp)
    assert advanced_row.property("activeFocus") is True

    ring = _find_qml_child(advanced_row, "focusRing")
    assert ring is not None, "focusRing component not found inside row"
    assert ring.property("shown") is True

    # The whole ring, not just the row, sits inside the clipped scroller.
    top = ring.mapToScene(QPointF(0, 0)).y()
    bottom = ring.mapToScene(QPointF(0, ring.property("height"))).y()
    view_top = scroller.mapToScene(QPointF(0, 0)).y()
    view_bottom = scroller.mapToScene(QPointF(0, scroller.property("height"))).y()
    assert top >= view_top, f"ring top {top} < view_top {view_top}"
    assert bottom <= view_bottom, f"ring bottom {bottom} > view_bottom {view_bottom}"


def test_escape_closes_manage_account_and_returns_focus(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = open_settings(qapp, window, "computer")
    quick = window._material_page._quick
    account_rows = named(root, "row_account")
    assert account_rows, "row_account not found"
    account_row = account_rows[0]
    account_row.forceActiveFocus()
    pump(qapp)
    assert quick.quickWindow().activeFocusItem() is account_row

    seen: dict[str, AccountDialog] = {}

    def run(dialog: AccountDialog) -> int:
        """Shown for real, then Esc pressed on it, as the student does."""
        dialog.show()
        wait_until(qapp, dialog.isVisible)
        seen["dialog"] = dialog
        assert dialog.findChild(QPushButton, "deleteAccount") is not None
        assert dialog.findChild(QPushButton, "accountClose") is not None
        escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        dialog.keyPressEvent(escape)
        return dialog.result()

    monkeypatch.setattr(AccountDialog, "exec", run)
    window._open_account()
    pump(qapp)

    dialog = seen["dialog"]
    assert not dialog.isVisible()
    assert dialog.result() == QDialog.DialogCode.Rejected
    # Focus returned to the QML opener
    assert quick.quickWindow().activeFocusItem() is account_row


def test_escape_closes_advanced_settings_and_returns_focus_to_its_row(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = open_settings(qapp, window, "look")
    quick = window._material_page._quick
    advanced_rows = named(root, "openAdvanced")
    assert advanced_rows, "openAdvanced not found"
    advanced_row = advanced_rows[0]
    advanced_row.forceActiveFocus()
    pump(qapp)

    settings_panel = panel(window)
    settings_panel.openAdvanced()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    pump(qapp)
    assert settings_panel._page == "advanced"

    window.activateWindow()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    pump(qapp)

    assert settings_panel._page == "sections"
    assert quick.quickWindow().activeFocusItem() is advanced_row
