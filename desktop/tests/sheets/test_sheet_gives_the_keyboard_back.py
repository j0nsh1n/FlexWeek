"""A sheet gives the keyboard back to what had it when it closes, if that is still there and nobody
else took it meanwhile: hours that were taken out of the window while the sheet closed get it on their
next showing, and never from another active window, field, page or open modal."""

# ruff: noqa: E402
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QStackedWidget, QVBoxLayout, QWidget

from desktop.native.widgets import Dialog, _give_focus_back


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-sheet-focus-test"])


def _hours_waiting_to_be_shown(qapp, host: QWidget) -> tuple[QWidget, QWidget]:
    """Hours that owned the keyboard, then left the window the way Bento re-lays tiles."""
    hours = QWidget(host)
    hours.setObjectName("hoursCanvas")
    hours.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    hours.show()
    hours.setFocus()
    qapp.processEvents()
    assert hours.hasFocus()
    holder = QWidget()
    hours.hide()
    hours.setParent(holder)
    qapp.processEvents()
    _give_focus_back(hours)
    return hours, holder


def test_hours_get_the_keyboard_back_if_they_were_hidden_while_the_sheet_closed(qapp) -> None:
    """Bento takes reused hours out of the grid and hides them while it re-lays tiles. The sheet's
    return can land in that gap, after the hours have left the window."""
    window = QWidget()
    window.resize(200, 120)
    window.show()
    window.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, window)
    hours.setParent(window)
    hours.show()
    qapp.processEvents()
    assert hours.hasFocus()
    holder.deleteLater()
    window.deleteLater()
    qapp.processEvents()


def test_hidden_hours_do_not_take_the_keyboard_from_another_active_window(qapp, monkeypatch) -> None:
    window = QWidget()
    window.resize(200, 120)
    window.show()
    window.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, window)
    other = QWidget()
    other.resize(160, 80)
    other.show()
    box = QWidget(other)
    box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    other.activateWindow()
    box.setFocus()
    qapp.processEvents()
    assert QApplication.activeWindow() is other
    activations = []
    monkeypatch.setattr(window, "activateWindow", lambda: activations.append(True))
    hours.setParent(window)
    hours.show()
    qapp.processEvents()
    assert QApplication.activeWindow() is other
    assert activations == []
    assert not hours.hasFocus()
    holder.deleteLater()
    other.deleteLater()
    window.deleteLater()
    qapp.processEvents()


def test_hidden_hours_do_not_take_the_keyboard_from_another_field_or_page(qapp) -> None:
    host = QWidget()
    host.resize(320, 200)
    host.show()
    host.activateWindow()
    week = QWidget(host)
    page = QWidget(host)
    week.setGeometry(0, 0, 320, 90)
    page.setGeometry(0, 100, 320, 90)
    week.show()
    page.show()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, week)
    field = QLineEdit(page)
    field.show()
    host.activateWindow()
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus()
    hours.setParent(week)
    hours.show()
    qapp.processEvents()
    assert field.hasFocus()
    assert not hours.hasFocus()
    holder.deleteLater()
    host.deleteLater()
    qapp.processEvents()


def test_hidden_hours_do_not_take_the_keyboard_from_an_open_modal(qapp) -> None:
    host = QWidget()
    host.resize(320, 180)
    host.show()
    host.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, host)
    dialog = QDialog(host)
    dialog.setModal(True)
    edit = QLineEdit(dialog)
    dialog.resize(200, 80)
    dialog.show()
    edit.setFocus()
    qapp.processEvents()
    assert QApplication.activeModalWidget() is dialog
    assert edit.hasFocus()
    hours.setParent(host)
    hours.show()
    qapp.processEvents()
    assert QApplication.activeModalWidget() is dialog
    assert edit.hasFocus()
    assert not hours.hasFocus()
    dialog.close()
    holder.deleteLater()
    host.deleteLater()
    qapp.processEvents()


def test_deferred_show_without_active_window_is_consumed_and_cannot_steal_later(qapp) -> None:
    host = QWidget()
    host.show()
    host.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, host)
    assert hasattr(hours, "_fw_focus_when_shown")
    QApplication.setActiveWindow(None)
    qapp.processEvents()
    assert QApplication.activeWindow() is None
    hours.setParent(host)
    hours.show()
    qapp.processEvents()
    assert not hasattr(hours, "_fw_focus_when_shown")
    assert not hours.hasFocus()
    hours.hide()
    field = QLineEdit(host)
    field.show()
    QApplication.setActiveWindow(host)
    host.activateWindow()
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus()
    hours.show()
    qapp.processEvents()
    assert field.hasFocus()
    holder.deleteLater()
    host.close()
    host.deleteLater()
    qapp.processEvents()


def test_deferred_show_waits_for_stacked_page_reentry_and_is_consumed(qapp) -> None:
    host = QWidget()
    layout = QVBoxLayout(host)
    pages = QStackedWidget(host)
    layout.addWidget(pages)
    week, other = QWidget(), QWidget()
    pages.addWidget(week)
    pages.addWidget(other)
    host.show()
    host.activateWindow()
    qapp.processEvents()
    hours, holder = _hours_waiting_to_be_shown(qapp, week)
    field = QLineEdit(other)
    field.show()
    pages.setCurrentWidget(other)
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus()
    hours.setParent(week)
    hours.show()
    qapp.processEvents()
    assert not hours.isVisible()
    assert hasattr(hours, "_fw_focus_when_shown")
    assert field.hasFocus()
    pages.setCurrentWidget(week)
    qapp.processEvents()
    assert hours.isVisible()
    assert not hasattr(hours, "_fw_focus_when_shown")
    pages.setCurrentWidget(other)
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus()
    assert not hasattr(hours, "_fw_focus_when_shown")
    holder.deleteLater()
    host.close()
    host.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("new_owner", ["field", "modal"])
def test_queued_sheet_close_checks_new_owner_on_visible_target(qapp, new_owner) -> None:
    host = QWidget()
    host.resize(320, 180)
    hours = QWidget(host)
    hours.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    hours.show()
    host.show()
    host.activateWindow()
    hours.setFocus()
    qapp.processEvents()
    assert hours.hasFocus()
    sheet = Dialog(host, sheet=True)
    sheet.card_body("Test sheet")
    sheet.show()
    qapp.processEvents()
    sheet.return_focus_to(hours)
    if new_owner == "modal":
        owner = QDialog(host)
        owner.setModal(True)
        field = QLineEdit(owner)
        owner.show()
    else:
        owner = host
        field = QLineEdit(host)
        field.show()
        host.activateWindow()
    field.setFocus()
    qapp.processEvents()
    assert field.hasFocus()
    if new_owner == "modal":
        assert QApplication.activeModalWidget() is owner
    sheet.hide()
    assert hours.isVisible()
    qapp.processEvents()
    assert field.hasFocus()
    if new_owner == "modal":
        assert QApplication.activeModalWidget() is owner
        owner.close()
    sheet.deleteLater()
    host.close()
    host.deleteLater()
    qapp.processEvents()
