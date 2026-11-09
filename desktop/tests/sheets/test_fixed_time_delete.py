"""Deleting a fixed time: it asks first, says exactly what goes, does nothing when refused, and the notice
that follows offers Undo. The question sheet's colours (the Delete answer red, Cancel plain) are a picture:
desktop/tests/pictures/screens_sheets_h8.py (sheets.delete-fixed-time-question, sheets.sign-out-question).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QWidget

from backend import clock as wall_clock
from desktop.native import widgets
from desktop.native.calendar import date_for_day
from desktop.native.widgets import BlockDialog, ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_soccer import soccer
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import host, qapp, settled  # noqa: F401


def test_delete_asks_first_and_does_nothing_when_refused(
    qapp: QApplication,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    host: QWidget,  # noqa: F811
) -> None:
    asked: list[tuple[str, str, str]] = []
    answer = [False]

    def confirm(_parent, title: str, question: str, yes: str) -> bool:
        asked.append((title, question, yes))
        return answer[0]

    monkeypatch.setattr(widgets, "confirm", confirm)
    dialog = BlockDialog(host, soccer())
    dialog.show()
    dialog.delete_button.click()
    assert asked == [
        (
            "Delete fixed time",
            "Delete Soccer practice on every Tue and Thu this week?",
            "Delete",
        )
    ]
    assert dialog.result() != QDialog.DialogCode.Accepted and dialog.deleted() is False
    assert dialog.isVisible(), "refusing leaves the editor open"
    answer[0] = True
    dialog.delete_button.click()
    assert dialog.deleted() is True and dialog.result() == QDialog.DialogCode.Accepted
    one_day = BlockDialog(host, soccer(), occurrence_day=3)
    one_day.scope_occurrence.setChecked(True)
    one_day.delete_button.click()
    today = wall_clock.today()
    occurrence_date = today - timedelta(days=today.weekday()) + timedelta(days=3)
    date_text = f"{occurrence_date.day} {occurrence_date.strftime('%b')}"
    assert asked[-1] == (
        "Delete fixed time",
        f"Delete Soccer practice on Thursday {date_text} only?",
        "Delete",
    )


def test_a_deleted_block_can_be_undone_from_the_notice(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = window.session
    session.add_block(soccer())
    session.save()
    settled(qapp, window)
    monkeypatch.setattr(widgets, "confirm", lambda *_args: True)
    dialog = BlockDialog(window, session.blocks[0])

    def run() -> int:
        dialog.show()
        dialog.delete_button.click()
        return dialog.result()

    monkeypatch.setattr(dialog, "exec", run, raising=False)
    window._commit_block(dialog)
    settled(qapp, window)
    assert session.blocks == []
    assert window.toast.text() == "Deleted Soccer practice from this week."
    assert window.toast.button.accessibleName() == "Undo" and window.toast.button.text().startswith("Undo")
    window.toast.button.click()
    wait_until(qapp, lambda: [block["id"] for block in session.blocks] == ["soccer"])


def test_the_question_before_deleting_has_a_delete_answer_and_cancel_is_the_one_enter_gives(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    question = "Delete Soccer practice? You can undo this."
    box = widgets.confirm_sheet(window, "Delete fixed time", question, "Delete")
    box.show()
    qapp.processEvents()
    yes = box.buttons["yes"]
    cancel = box.buttons["stay"]
    shown_buttons = [button.text() for button in box.buttons.values() if button.isVisible()]
    assert sorted(shown_buttons) == ["Cancel", "Delete"]
    assert cancel.isDefault() and not yes.isDefault(), "Enter pressed out of habit changes nothing"
    assert yes.property("danger"), "the Delete answer is the destructive kind (drawn red)"
    assert not cancel.property("danger"), "Cancel is plain"
    box.close()


def test_the_sign_out_question_is_not_a_destructive_answer(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """Signing out keeps everything, so its answer is filled in the accent, not drawn as a danger."""
    leave = widgets.confirm_sheet(window, "Sign out", "Sure?", "Sign out", danger=False)
    leave.show()
    qapp.processEvents()
    assert not leave.buttons["yes"].property("danger")
    leave.close()


def test_setup_delete_from_one_day_uses_one_sheet_and_offers_undo(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = {
        "id": "activity-1",
        "title": "Soccer",
        "kind": "locked",
        "category": "extra",
        "start": "16:00",
        "duration_min": 90,
        "days": [1, 3],
    }
    window.session.set_setup_blocks([setup])
    shown: list[ConfirmSheet] = []

    def choose_week(sheet: ConfirmSheet) -> int:
        shown.append(sheet)
        sheet.answer = "week"
        return 0

    monkeypatch.setattr(ConfirmSheet, "exec", choose_week)
    dialog = BlockDialog(window, setup, occurrence_day=1)
    dialog._delete()
    assert len(shown) == 1
    sheet = shown[0]
    assert sheet.windowTitle() == "Delete Soccer?"
    occurrence_date = date.fromisoformat(date_for_day(window.session.week_start, 1))
    date_text = f"{occurrence_date.day} {occurrence_date.strftime('%b')}"
    assert sheet.question.text() == f"Delete Soccer on Tuesday {date_text} only? Earlier weeks keep it."
    assert sheet.buttons["day"].isDefault()
    assert [button.text() for button in sheet.buttons.values()] == [
        "Cancel",
        "This day only",
        "This week only",
        "This week and later",
    ]
    window._delete_block(
        dialog.block(), dialog.scope(), dialog.occurrence_day(), every_week=dialog.delete_every_week()
    )
    assert len(shown) == 1, "the week choice did not open a second Setup confirmation"
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    soccer_now = next(block for block in window.session.blocks if block["id"] == "activity-1")
    assert soccer_now["missed_days"] == [1, 3]
    assert window.toast.text() == "Deleted Soccer from this week."
    assert window.toast.button.isVisible() and window.toast.button.text().startswith("Undo")
    window._undo_from_notice()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    restored = next(block for block in window.session.blocks if block["id"] == "activity-1")
    assert restored.get("missed_days", []) == []


def test_deleting_a_repeating_block_names_every_selected_day(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = BlockDialog(window, soccer(), occurrence_day=1)
    asked: list[tuple[str, str, str]] = []

    def yes(_parent, title: str, question: str, button: str) -> bool:
        asked.append((title, question, button))
        return True

    monkeypatch.setattr("desktop.native.widgets.confirm", yes)
    dialog.scope_series.setChecked(True)
    dialog._delete()
    assert asked == [
        (
            "Delete fixed time",
            "Delete Soccer practice on every Tue and Thu this week?",
            "Delete",
        )
    ]
