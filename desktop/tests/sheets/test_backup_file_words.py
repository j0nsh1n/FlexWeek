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
from desktop.native import window as window_module
from desktop.native.reuse import week_label
from desktop.native.settings import AccountDialog, TransferPreviewDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import fixed
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


def test_replacing_a_week_from_a_file_asks_in_a_dialog_with_the_real_choice(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = window.session
    session.add_block(fixed("school", "School", 0, "08:00"))
    path = tmp_path / "week.json"
    path.write_text(json.dumps(session.week_file()))
    asked: list[tuple[str, str, str]] = []

    def refuse(_parent: object, title: str, question: str, yes: str, **_more: object) -> bool:
        asked.append((title, question, yes))
        return False

    monkeypatch.setattr(window_module, "confirm", refuse)
    monkeypatch.setattr(AccountDialog, "exec", lambda dialog: _choose(dialog, "import-week"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    window._open_account()
    label = week_label(session.week_start, window._today())
    assert asked == [
        (
            "Replace week",
            f"Replace everything in {label} with this file? Other weeks aren't changed. You can undo this.",
            "Replace week",
        )
    ]


@pytest.mark.parametrize("action", ["import", "import-week"])
def test_a_file_that_will_not_open_says_how_to_choose_one(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    action: str,
) -> None:
    missing = tmp_path / "gone.json"
    monkeypatch.setattr(AccountDialog, "exec", lambda dialog: _choose(dialog, action))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(missing), ""))
    window._open_account()
    # Import week or day names week and day files; the backup import keeps its own wording.
    expected = {
        "import": "Couldn't open that file. Choose a FlexWeek backup file (it ends in .json).",
        "import-week": "Couldn't open that file. Choose a FlexWeek week or day file (it ends in .json).",
    }[action]
    assert window.session.message == expected


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
    window._show_page("authPage")
    window.forgot_button.click()
    qapp.processEvents()
    note = window.auth_note.text()
    assert note.startswith("Use one of the recovery codes you saved when you made your account.")
    assert "Lost them too?" in note
    assert "Create a new account and import a backup file" in note
    assert "start fresh" in note


def test_create_account_asks_for_a_backup_now_and_then(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window._show_page("authPage")
    window.auth_switch.click()
    qapp.processEvents()
    assert "Export a backup file now and then" in window.auth_note.text()
