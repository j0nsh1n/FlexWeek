# ruff: noqa: F811

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyleOptionViewItem

from desktop.native.weekmodel import Waiting
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import CREATE, RESET, SIGN_IN, NativeWindow
from desktop.tests.window_support import qapp, server, signed_out, window  # noqa: F401


@pytest.mark.parametrize(
    ("mode", "field_name"),
    [(SIGN_IN, "password"), (CREATE, "password"), (RESET, "recovery_code")],
)
def test_enter_submits_the_active_auth_card_and_focuses_its_first_problem(
    qapp, signed_out: NativeWindow, mode: str, field_name: str
) -> None:
    card = signed_out
    card._entry_mode = mode
    card._sync_auth_mode()
    card.username.setText("jo" if mode == CREATE else "")
    card.password.setText("short" if mode == CREATE else "anything")
    card.recovery_code.setText("")
    card.new_recovery_password.setText("")
    field = getattr(card, field_name)
    field.setFocus()

    QTest.keyClick(field, Qt.Key.Key_Return)
    qapp.processEvents()

    assert card.focusWidget() is card.username
    assert card.username_problem.isVisible()
    enter_problem = card.username.accessibleDescription()

    card._clear_auth_problems()
    card.username.setText("jo" if mode == CREATE else "")
    card.password.setText("short" if mode == CREATE else "anything")
    card.recovery_code.setText("")
    card.new_recovery_password.setText("")
    {SIGN_IN: card.sign_in_button, CREATE: card.create_button, RESET: card.recover_button}[mode].click()
    qapp.processEvents()

    assert card.username.accessibleDescription() == enter_problem
    assert card.focusWidget() is card.username


def test_not_placed_rows_keep_each_open_sessions_length(qapp, window: NativeWindow) -> None:
    rail = window.rail
    rail.set_waiting(
        (
            Waiting("hist-1", "History essay", "assignments", 60, "history", None, ""),
            Waiting("hist-2", "History essay", "assignments", 30, "history", None, ""),
        ),
        {"history": 90},
    )

    assert [chip.length for chip in rail.chips()] == ["1 h", "30 min"]
    assert sum((60, 30)) == 90


def test_focus_rows_allocate_height_for_long_titles_without_overlap(qapp, window: NativeWindow) -> None:
    rail = window.rail
    rail.set_tasks(
        [
            {
                "id": "long",
                "day": 0,
                "start": "19:00",
                "title": (
                    "A long history essay title with many words that must wrap across lines before focus"
                ),
            },
            {"id": "short", "day": 1, "start": "19:00", "title": "Math"},
        ],
        0,
    )
    qapp.processEvents()

    tasks = rail.tasks
    rows = [tasks.visualItemRect(tasks.item(index)) for index in range(tasks.count())]
    delegate = tasks.itemDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, tasks.viewport().width(), 0)
    lines, _below, _timing = delegate.row_lines(tasks.indexFromItem(tasks.item(0)), option.rect.width())
    assert len(lines) > 1
    expected = delegate.sizeHint(option, tasks.indexFromItem(tasks.item(0))).height()
    assert tasks.item(0).sizeHint().height() >= expected
    assert rows[0].height() >= expected
    assert rows[0].height() > 30
    assert rows[1].top() > rows[0].bottom()
    assert tasks.height() >= sum(tasks.item(index).sizeHint().height() for index in range(tasks.count()))


def test_homework_due_date_keys_step_by_day_and_by_week(qapp) -> None:
    dialog = HomeworkDialog(None, today="2026-10-05")
    field = dialog.due.date
    field.setDate(QDate(2026, 10, 9))
    field.setFocus()

    QTest.keyClick(field, Qt.Key.Key_Up)
    assert field.date() == QDate(2026, 10, 10)
    QTest.keyClick(field, Qt.Key.Key_Up)
    assert field.date() == QDate(2026, 10, 11)
    QTest.keyClick(field, Qt.Key.Key_PageDown)
    assert field.date() == QDate(2026, 10, 18)
    QTest.keyClick(field, Qt.Key.Key_Down)
    assert field.date() == QDate(2026, 10, 17)
