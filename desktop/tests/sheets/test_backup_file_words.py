"""What a student reads when a backup or week file is imported, replaced, will not open or will not save,
and when a lost recovery code is the problem.

Expected words come from the 0.19.0 wording audit's suggestions (03-wording-audit.md), not from the
code's output.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QPlainTextEdit, QPushButton, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.reuse import week_label
from desktop.native.settings import AccountDialog, TransferPreviewDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import card_phase
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, qapp  # noqa: F401

PREVIEW = {
    "source_username": "joo2",
    "changes": {
        "weeks": {"added": ["2026-10-05"], "changed": ["2026-10-12", "2026-10-19"], "removed": []},
        "assignments": {"added": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "changed": [], "removed": []},
        "preferences_changed": True,
    },
}


def texts(root: QWidget) -> list[str]:
    return [label.text() for label in root.findChildren(QLabel)]


def _choose(dialog: AccountDialog, action: str) -> QDialog.DialogCode:
    dialog.action = action
    return QDialog.DialogCode.Accepted


def test_the_import_preview_counts_what_changes_in_words(qapp: QApplication) -> None:  # noqa: F811
    dialog = TransferPreviewDialog(None, PREVIEW)
    assert dialog.windowTitle() == "Import backup file?"
    assert texts(dialog) == [
        "From joo2's backup: adds 1 week and replaces 2 of your weeks. 3 homework change. "
        "Your settings will be replaced.",
        "FlexWeek saves a restore point first, so you can go back.",
    ]
    assert dialog.findChildren(QPlainTextEdit) == []
    ok = [b for b in dialog.findChildren(QPushButton) if b.text() == "Import"]
    assert len(ok) == 1
    free(dialog)


def test_an_import_that_changes_nothing_says_so(qapp: QApplication) -> None:  # noqa: F811
    dialog = TransferPreviewDialog(None, {"source_username": "joo2", "changes": {}})
    assert texts(dialog)[0] == "From joo2's backup: Nothing in it is different from your account."
    free(dialog)


def test_a_file_for_another_week_says_nothing_was_imported_and_where_to_go(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    # The test holds its own clock, so "another week" is the week after the open one on any day.
    monday = datetime.fromisoformat(session.week_start) + timedelta(hours=10)
    CLOCK.set(monday)
    other_start = (monday + timedelta(days=7)).date().isoformat()
    other = {**session.week_file(), "week_start": other_start}
    other_label = week_label(other_start, session.today_iso())
    assert session.import_week_file(json.dumps(other)) is False
    assert session.message == (
        f"Nothing imported: this file is for {other_label}. Go to that week, then import again."
    )


def test_a_file_that_will_not_be_written_says_to_choose_another_folder(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    nowhere = tmp_path / "no-such-folder" / "week.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: (str(nowhere), ""))
    window._write_json("week.json", {})
    assert window.session.message == "Couldn't save there. Choose another folder, like Documents."


def test_manage_account_calls_the_file_a_backup_file(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = AccountDialog(window, 0, None)
    names = {b.objectName(): b.text() for b in dialog.findChildren(QPushButton)}
    assert names["exportAccount"] == "Export backup file"
    assert names["importAccount"] == "Import backup file"
    free(dialog)


def test_reset_password_says_what_to_do_without_recovery_codes(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window.session.logout()
    wait_until(qapp, lambda: card_phase(window) == "sign-in")
    bridge = window._account_bridge()
    bridge.showReset()
    qapp.processEvents()
    note = bridge.note
    assert note.startswith("Use one of the recovery codes you saved when you made your account.")
    assert "Lost them too?" in note
    assert "Create a new account and import a backup file" in note
    assert "start fresh" in note


def test_create_account_asks_for_a_backup_now_and_then(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window.session.logout()
    wait_until(qapp, lambda: card_phase(window) == "sign-in")
    bridge = window._account_bridge()
    bridge.showCreate()
    qapp.processEvents()
    assert "Export a backup file now and then" in bridge.note
