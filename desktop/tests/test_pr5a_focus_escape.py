# ruff: noqa: F811
"""Tests for FIX-SPEC PR 5a items B, C, D, E, J:
- B: Advanced settings row ring + scroll into view (ensureVisible)
- C: Esc closes Manage account, focus returns to opener, focus rings
- D: Widgets fixed-time dialog discard prompt on Esc; look editor Esc and Tab to Done
- E: Back to Material button and More menu entry in Widgets
- J: Esc closes Advanced settings, focus back to its row
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from desktop.native.settings import AccountDialog
from desktop.native.widgets import BlockDialog, ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.test_dialogs_look import shown
from desktop.tests.test_layouts_window import settled
from desktop.tests.test_look_editor import open_editor
from desktop.tests.test_material_settings import (
    _named,
    _open_settings,
    _panel,
    _pump,
    _qml,
)
from desktop.tests.test_material_window import (  # noqa: F401
    _show_material,
    qapp,
    window,
)
from desktop.tests.window_support import free


def _find_qml_child(parent, name: str):
    for child in parent.childItems():
        if child.objectName() == name:
            return child
        found = _find_qml_child(child, name)
        if found is not None:
            return found
    return None


# --- Item B ---
def test_advanced_settings_row_shows_the_ring_and_scrolls_into_view_on_tab(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "look")
    scroller = _qml(root, "lookSection")
    advanced_rows = _named(root, "openAdvanced")
    assert advanced_rows, "openAdvanced row not found"
    advanced_row = advanced_rows[0]

    # Verify initial scroll position is 0
    scroller.setProperty("contentY", 0.0)
    _pump(qapp)

    # Force active focus on the Advanced settings row
    advanced_row.forceActiveFocus()
    _pump(qapp)
    assert advanced_row.property("activeFocus") is True

    # Focus ring is shown
    ring = _find_qml_child(advanced_row, "focusRing")
    assert ring is not None, "focusRing component not found inside row"
    assert ring.property("shown") is True

    # Verify ensureVisible scrolled it into view
    top = advanced_row.mapToScene(QPointF(0, 0)).y()
    bottom = advanced_row.mapToScene(QPointF(0, advanced_row.property("height"))).y()
    view_top = scroller.mapToScene(QPointF(0, 0)).y()
    view_bottom = scroller.mapToScene(QPointF(0, scroller.property("height"))).y()
    assert top >= view_top - 1, f"top {top} < view_top {view_top}"
    assert bottom <= view_bottom + 1, f"bottom {bottom} > view_bottom {view_bottom}"

    window._use_widgets_styles()


# --- Item C ---
def test_escape_closes_manage_account_and_returns_focus(qapp: QApplication, window: NativeWindow) -> None:
    # Test from Material settings computer section
    root = _open_settings(qapp, window, "computer")
    quick = window._material_page._quick
    account_rows = _named(root, "row_account")
    assert account_rows, "row_account not found"
    account_row = account_rows[0]
    account_row.forceActiveFocus()
    _pump(qapp)
    assert quick.quickWindow().activeFocusItem() is account_row

    seen: dict[str, object] = {}

    def on_dialog() -> None:
        dialog = QApplication.activeModalWidget()
        seen["dialog"] = dialog
        try:
            assert isinstance(dialog, AccountDialog)
            # Check controls have focus ring styling / keyfocus capability
            delete_btn = dialog.findChild(QPushButton, "deleteAccount")
            close_btn = dialog.findChild(QPushButton, "accountClose")
            assert delete_btn is not None
            assert close_btn is not None
            assert delete_btn.property("danger") is True
            assert delete_btn.property("outlined") is True
            dialog_css = dialog.styleSheet()
            assert 'QPushButton[danger="true"][keyfocus="true"]:focus' in dialog_css
            assert 'QPushButton[outlined="true"][keyfocus="true"]:focus' in dialog_css
            # Press Escape on dialog via keyPressEvent
            dialog.keyPressEvent(
                QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
            )
        except BaseException as error:
            seen["error"] = error
            if dialog is not None and hasattr(dialog, "reject"):
                dialog.reject()

    QTimer.singleShot(350, on_dialog)
    window._open_account()
    _pump(qapp)

    if "error" in seen:
        raise seen["error"]  # type: ignore[misc]

    dialog = seen.get("dialog")
    assert dialog is not None
    assert not dialog.isVisible()
    # Focus returned to the QML opener
    assert quick.quickWindow().activeFocusItem() is account_row

    window._use_widgets_styles()


# --- Item D ---
def test_escape_on_a_typed_fixed_time_asks_to_discard(qapp: QApplication, window: NativeWindow) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        _pump(qapp)
        assert dialog.isVisible()
        # Type into title
        dialog.title.setText("Piano lesson")
        _pump(qapp)

        # Press Esc: should prompt to discard
        seen: dict[str, object] = {}

        def handle_confirm() -> None:
            try:
                confirm_sheet = QApplication.activeModalWidget()
                assert isinstance(confirm_sheet, ConfirmSheet)
                assert confirm_sheet.windowTitle() == "Discard what you typed?"
                seen["stay_shown"] = True
                # Click stay
                confirm_sheet.buttons["stay"].click()
            except BaseException as e:
                seen["error"] = e

        QTimer.singleShot(0, handle_confirm)
        dialog.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )
        _pump(qapp)
        if "error" in seen:
            raise seen["error"]  # type: ignore[misc]
        assert seen.get("stay_shown") is True
        # Stays open
        assert dialog.isVisible()

        # Press Esc again, choose discard
        def handle_discard() -> None:
            try:
                confirm_sheet = QApplication.activeModalWidget()
                assert isinstance(confirm_sheet, ConfirmSheet)
                seen["discard_shown"] = True
                confirm_sheet.buttons["discard"].click()
            except BaseException as e:
                seen["error"] = e

        QTimer.singleShot(0, handle_discard)
        dialog.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )
        _pump(qapp)
        if "error" in seen:
            raise seen["error"]  # type: ignore[misc]
        assert seen.get("discard_shown") is True
        # Closed
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
    finally:
        free(dialog)


def test_escape_on_an_empty_fixed_time_just_closes(qapp: QApplication, window: NativeWindow) -> None:
    dialog = shown(qapp, BlockDialog(window))
    try:
        dialog.activateWindow()
        _pump(qapp)
        assert dialog.isVisible()
        # Untouched: pressing Esc closes immediately without asking
        dialog.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )
        _pump(qapp)
        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
    finally:
        free(dialog)


def test_escape_closes_the_look_editor(qapp: QApplication, window: NativeWindow) -> None:
    window._use_widgets_styles()
    page, editor = open_editor(qapp, window)
    try:
        window.activateWindow()
        _pump(qapp)
        assert editor.isVisible()

        # Esc closes the look editor
        editor.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )
        _pump(qapp)
        assert page.editor is None or not page.editor.isVisible()
    finally:
        if page.editor is not None:
            page.editor.leave()
            _pump(qapp)
        window._close_settings(save=False)


def test_tab_reaches_done_in_the_look_editor_in_five_presses(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._use_widgets_styles()
    page, editor = open_editor(qapp, window)
    try:
        window.activateWindow()
        _pump(qapp)
        assert editor.isVisible()

        editor.back.setFocus()
        _pump(qapp)
        assert editor.back.hasFocus() or QApplication.focusWidget() is editor.back

        presses = 0
        for _ in range(5):
            QTest.keyClick(editor, Qt.Key.Key_Tab)
            _pump(qapp)
            presses += 1
            if editor.done.hasFocus() or QApplication.focusWidget() is editor.done:
                break

        assert editor.done.hasFocus() or QApplication.focusWidget() is editor.done
        assert presses <= 5
    finally:
        if page.editor is not None:
            page.editor.finish()
            _pump(qapp)
        window._close_settings(save=False)


# --- Item E ---
def test_back_to_material_button_in_widgets_settings_switches_style(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._use_widgets_styles()
    window._open_settings()
    settled(qapp, window)
    _pump(qapp)

    btn = window.findChild(QPushButton, "chooseMaterial")
    assert btn is not None
    assert btn.accessibleName() == "Back to Material"
    assert btn.focusPolicy() == Qt.FocusPolicy.StrongFocus

    btn.click()
    settled(qapp, window)
    _pump(qapp)
    assert window._surface == "material"
    window._use_widgets_styles()


def test_back_to_material_in_the_widgets_more_menu(qapp: QApplication, window: NativeWindow) -> None:
    window._use_widgets_styles()
    settled(qapp, window)
    _pump(qapp)

    actions = [a for a in window.more_menu.actions() if a.text() == "Back to Material"]
    assert actions, "Back to Material action not found in More menu"
    actions[0].trigger()
    settled(qapp, window)
    _pump(qapp)
    assert window._surface == "material"
    window._use_widgets_styles()


# --- Item J ---
def test_escape_closes_advanced_settings_and_returns_focus_to_its_row(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "look")
    quick = window._material_page._quick
    advanced_rows = _named(root, "openAdvanced")
    assert advanced_rows, "openAdvanced not found"
    advanced_row = advanced_rows[0]
    advanced_row.forceActiveFocus()
    _pump(qapp)

    panel = _panel(window)
    panel.openAdvanced()
    settled(qapp, window)
    _pump(qapp)
    assert panel._page == "advanced"

    # Press Escape on the quick widget
    window.activateWindow()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    settled(qapp, window)
    _pump(qapp)

    assert panel._page == "sections"
    assert quick.quickWindow().activeFocusItem() is advanced_row

    window._use_widgets_styles()
