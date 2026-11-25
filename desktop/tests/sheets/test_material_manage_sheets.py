# ruff: noqa: F811
"""Manage account and Restore points as Material sheets (1.5.0 step 5b). Each opens from More or from
Settings, does what its Widgets dialog did through the real backend, asks before deleting, importing or
restoring, and the Widgets AccountDialog and RestoreDialog never open over Material. Expected words are the
Widgets copy and the requirement, not what the sheet prints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from desktop.native.account_copy import READ_WEEK_FAILED, REPLACE_WEEK_QUESTION
from desktop.native.files import EXPORT_FORMAT
from desktop.native.reuse import week_label
from desktop.native.window import NativeWindow
from desktop.tests.material_support import focus_quick, named, pump, quick_of, quick_window_of
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME

NEW_PASSWORD = "another-long-test-password"


def _refuse(name: str):
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"the Widgets {name} opened over Material")

    return refuse


def _root(shell: NativeWindow) -> QObject:
    return shell._material_page.root


def _quick(shell: NativeWindow):
    quick = quick_of(shell)
    shell.activateWindow()
    focus_quick(shell)
    return quick


def _one(shell: NativeWindow, name: str) -> QObject:
    found = named(_root(shell), name)
    assert len(found) == 1, f"{name}: {len(found)} found"
    return found[0]


def _text(shell: NativeWindow, name: str) -> str:
    return str(_one(shell, name).property("text"))


def _click(shell: NativeWindow, name: str) -> None:
    """Scrolls the sheet's body until the item shows, then taps it. A tap below the fold would land on the
    scrim and close the sheet, as it would for a student."""
    quick = _quick(shell)
    item = _one(shell, name)
    body = named(_root(shell), "sheetBody")
    if body:
        scroller = body[0]
        top = item.mapToItem(scroller.property("contentItem"), 0, 0).y()
        visible = float(scroller.property("height"))
        if top + item.height() > float(scroller.property("contentY")) + visible or top < float(
            scroller.property("contentY")
        ):
            scroller.setProperty("contentY", max(0.0, top - 16))
            pump(QApplication.instance(), 5)
    spot = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=spot.toPoint())
    pump(QApplication.instance(), 20)


def _press(shell: NativeWindow, key: Qt.Key) -> None:
    QTest.keyClick(_quick(shell), key)
    pump(QApplication.instance(), 20)


def _type(shell: NativeWindow, name: str, words: str) -> None:
    _one(shell, name).setProperty("text", words)
    pump(QApplication.instance(), 5)


def _kind(sheets) -> str:
    return str(sheets.property("kind"))


def _asking(sheets) -> str:
    return str(sheets.property("ask").get("id", ""))


def _answer_buttons(sheets) -> dict[str, str]:
    return {a["id"]: a["label"] for a in sheets.property("ask")["answers"]}


def _said(shell: NativeWindow, words: str, qapp: QApplication) -> None:
    wait_until(qapp, lambda: shell.session.message == words, what=lambda: shell.session.message)


def _open_account(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    sheets.openMore()
    pump(qapp, 10)
    sheets.moreAction("accountButton")
    pump(qapp, 40)
    assert _kind(sheets) == "account"


# Opening ------------------------------------------------------------------------------------------


def test_more_has_account_and_copies_of_this_week_and_nothing_opens_a_widgets_dialog(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheets.openMore()
    rows = {row["id"]: row for row in sheets.moreEntries if row["id"]}
    assert rows["accountButton"]["label"] == "Account"
    assert rows["restoreButton"]["label"] == "Copies of this week"
    sheets.moreAction("accountButton")
    pump(qapp, 40)
    assert _kind(sheets) == "account"
    assert _text(shell, "sheetTitle") == "Manage account"
    sheets.forceClose()
    sheets.moreAction("restoreButton")
    pump(qapp, 40)
    assert _kind(sheets) == "restore"
    assert _text(shell, "sheetTitle") == "Saved copies"
    # The window's own entry points, which Settings and the keys use, land on the sheets too.
    sheets.forceClose()
    shell._open_account()
    pump(qapp, 40)
    assert _kind(sheets) == "account"
    sheets.forceClose()
    sheets.openRestore()
    pump(qapp, 40)
    assert _kind(sheets) == "restore"


def test_settings_this_computer_manage_account_opens_the_sheet(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel = shell._material_page.bridge.settingsBridge
    panel.openAccount()
    pump(qapp, 40)
    assert _kind(sheets) == "account"


def test_the_account_sheet_has_the_widgets_words_and_hides_the_passwords(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    wait_until(qapp, lambda: shell.session.storage_info is not None)
    shell.session.recovery_remaining = 8
    _open_account(qapp, shell, sheets)
    assert _text(shell, "accountLocation") == (
        f"Signed in as {USERNAME}. Your week is saved on this computer, under this account."
    )
    assert _text(shell, "recoveryCount") == "8 unused recovery codes remain."
    form = sheets.property("form")
    assert form["passwordNote"] == "Your current password is needed for every change on this page."
    assert form["codesNote"] == "Each code signs you in once if you forget your password."
    assert form["dataNote"] == "Keep a copy of your account, or of one week or day, in a file."
    for name in ("currentPassword", "newPassword"):
        field = _one(shell, name)
        assert field.property("secret") is True and field.property("revealed") is False, "dots, not the words"
    shown = [
        str(item.property("text"))
        for name in (
            "changePassword",
            "replaceCodes",
            "exportAccount",
            "importAccount",
            "exportWeek",
            "exportDay",
            "importFile",
            "deleteAccount",
        )
        for item in named(_root(shell), name)
    ]
    assert shown == [
        "Change password",
        "Replace recovery codes",
        "Export backup file",
        "Import backup file",
        "Export week",
        "Export day",
        "Import week or day file",
        "Delete account",
    ]


def test_a_taller_account_sheet_shows_a_scroll_bar_and_every_action_is_reachable(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_account(qapp, shell, sheets)
    body = _one(shell, "sheetBody")
    bar = _one(shell, "sheetScrollBar")
    taller = float(body.property("contentHeight")) > float(body.property("height"))
    assert taller, "the sheet is taller than its room"
    assert bar.property("visible") is True, "the cue shows there is more below"
    assert float(bar.property("size")) < 1.0
    for name in ("exportDay", "importFile", "deleteAccount"):
        found = named(_root(shell), name)
        assert len(found) == 1 and found[0].property("visible") is True, name
    _click(shell, "deleteAccount")
    assert _asking(sheets) != "", "Delete account is reached by scrolling and asks first"


def test_no_recovery_codes_left_is_said_as_a_problem(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    shell.session.recovery_remaining = 0
    _open_account(qapp, shell, sheets)
    assert (
        _text(shell, "recoveryCount") == "No unused recovery codes remain. Replace them before signing out."
    )
    assert sheets.property("form")["codesProblem"] is True


# Account actions, through the real backend -----------------------------------------------------------


def test_replace_password_changes_it_on_the_server_and_a_wrong_one_is_refused(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", "not-my-password")
    _type(shell, "newPassword", NEW_PASSWORD)
    _click(shell, "changePassword")
    assert _kind(sheets) == "", "the sheet closes, as the Widgets dialog did"
    wait_until(qapp, lambda: not shell.session.busy)
    assert shell.session.message != "Password replaced."
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _type(shell, "newPassword", NEW_PASSWORD)
    _click(shell, "changePassword")
    _said(shell, "Password replaced.", qapp)
    # The server holds the new one now: the old one no longer opens the change.
    shell.session.change_password(PASSWORD, "x" * 20)
    wait_until(qapp, lambda: not shell.session.busy)
    assert shell.session.message != "Password replaced."
    shell.session.change_password(NEW_PASSWORD, PASSWORD)
    _said(shell, "Password replaced.", qapp)


def test_replace_recovery_codes_hands_over_new_codes_once(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    given: list[list[str]] = []
    shell.session.recovery_codes.connect(given.append)
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "replaceCodes")
    assert _kind(sheets) == ""
    wait_until(qapp, lambda: bool(given), what=lambda: shell.session.message)
    assert len(given[0]) == shell.session.recovery_remaining > 0
    assert shell.session.message == "Save these replacement recovery codes."


def test_replace_recovery_codes_with_a_wrong_password_gives_no_codes(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    given: list[list[str]] = []
    shell.session.recovery_codes.connect(given.append)
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", "not-my-password")
    _click(shell, "replaceCodes")
    wait_until(qapp, lambda: not shell.session.busy)
    assert given == []


def test_export_account_writes_the_backup_file_where_the_student_picked(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "backup.json"
    asked: list[str] = []

    def pick(_parent, _title, name, _filter):
        asked.append(name)
        return str(target), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(pick))
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "exportAccount")
    wait_until(qapp, lambda: target.exists(), what=lambda: shell.session.message)
    assert asked == [f"flexweek-account-{USERNAME}.json"]
    assert json.loads(target.read_text())["username"] == USERNAME
    _said(
        shell,
        f"Saved your backup file to {target}. Keep it private: it has all your weeks and homework.",
        qapp,
    )


def test_export_account_with_a_wrong_password_writes_nothing(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "backup.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", "not-my-password")
    _click(shell, "exportAccount")
    wait_until(qapp, lambda: not shell.session.busy)
    assert not target.exists()


def _backup(
    qapp: QApplication, shell: NativeWindow, sheets, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "exportAccount")
    wait_until(qapp, lambda: path.exists())
    wait_until(qapp, lambda: not shell.session.busy)


def test_import_backup_asks_first_and_only_imports_on_the_answer(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup.json"
    _backup(qapp, shell, sheets, backup, monkeypatch)
    applied: list[bool] = []
    real_apply = shell.session.apply_account_import
    monkeypatch.setattr(shell.session, "apply_account_import", lambda: applied.append(True) or real_apply())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(backup), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, "importAccount")
    assert _kind(sheets) == "", "the file is picked after the sheet has closed"
    wait_until(qapp, lambda: _asking(sheets) == "import-account", what=lambda: shell.session.message)
    ask = sheets.property("ask")
    assert ask["title"] == "Import backup file?"
    assert f"From {USERNAME}'s backup: " in ask["body"]
    assert ask["body"].endswith(
        "FlexWeek saves a copy of your current weeks and homework first, so you can go back."
    )
    assert _answer_buttons(sheets) == {"stay": "Cancel", "import": "Import"}
    assert applied == [], "nothing is imported before the answer"
    _press(shell, Qt.Key.Key_Escape)
    assert _asking(sheets) == "" and applied == []
    # Cancel leaves it too.
    _click_import_again(qapp, shell, sheets)
    sheets.answer("stay")
    assert applied == []
    _click_import_again(qapp, shell, sheets)
    sheets.answer("import")
    assert applied == [True]
    # The server saved its own "Before import" copy first, then took the file.
    wait_until(qapp, lambda: not shell.session.busy)
    shell.session._fetch_restore_points()
    wait_until(
        qapp,
        lambda: any(str(p["label"]).startswith("Before import — ") for p in shell.session.restore_points),
        what=lambda: str([p["label"] for p in shell.session.restore_points]),
    )


def _click_import_again(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    wait_until(qapp, lambda: not shell.session.busy)
    _open_account(qapp, shell, sheets)
    _click(shell, "importAccount")
    wait_until(qapp, lambda: _asking(sheets) == "import-account", what=lambda: shell.session.message)


def test_import_backup_that_is_not_a_backup_says_so_and_asks_nothing(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, "importAccount")
    assert (
        shell.session.message == "Couldn't open that file. Choose a FlexWeek backup file (it ends in .json)."
    )
    assert _asking(sheets) == ""


@pytest.mark.parametrize(
    ("row", "words"),
    [
        ("importAccount", "Couldn't open that file. Choose a FlexWeek backup file (it ends in .json)."),
        ("importFile", "Couldn't open that file. Choose a FlexWeek week or day file (it ends in .json)."),
    ],
)
def test_a_file_that_will_not_open_says_how_to_choose_one(
    qapp: QApplication,
    shell: NativeWindow,
    sheets,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    row: str,
    words: str,
) -> None:
    """Import backup names backup files; Import week or day names week and day files."""
    missing = tmp_path / "gone.json"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(missing), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, row)
    assert shell.session.message == words
    assert _asking(sheets) == ""


def test_delete_account_asks_first_and_cancel_leaves_the_sheet_as_it_was(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(shell.session, "delete_account", deleted.append)
    wait_until(qapp, lambda: shell.session.storage_info is not None)
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "deleteAccount")
    assert deleted == [], "nothing goes before the answer"
    assert _kind(sheets) == "account" and _asking(sheets) == "delete-account"
    ask = sheets.property("ask")
    assert ask["title"] == "Delete account"
    assert ask["body"] == (
        f"Delete the account {USERNAME}? Every week, all your homework and your settings are removed "
        "from this computer. This can't be undone."
    )
    assert _answer_buttons(sheets) == {"stay": "Cancel", "delete": f"Delete {USERNAME}"}
    assert ask["answers"][0]["default"] is True, "Enter pressed out of habit changes nothing"
    # Esc closes the question, not the sheet, and the typed password is still there.
    _press(shell, Qt.Key.Key_Escape)
    assert _asking(sheets) == "" and _kind(sheets) == "account"
    assert _text(shell, "currentPassword") == PASSWORD
    assert deleted == []
    _click(shell, "deleteAccount")
    sheets.answer("stay")
    assert deleted == [] and _kind(sheets) == "account"
    _click(shell, "deleteAccount")
    sheets.answer("delete")
    assert deleted == [PASSWORD]
    assert _kind(sheets) == "", "the sheet goes with the account"


def test_delete_account_removes_it_on_the_server_with_the_right_password(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    wait_until(qapp, lambda: shell.session.storage_info is not None)
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", "not-my-password")
    _click(shell, "deleteAccount")
    sheets.answer("delete")
    wait_until(qapp, lambda: not shell.session.busy)
    assert shell.session.account is not None, "a wrong password deletes nothing"
    _open_account(qapp, shell, sheets)
    _type(shell, "currentPassword", PASSWORD)
    _click(shell, "deleteAccount")
    sheets.answer("delete")
    wait_until(qapp, lambda: shell.session.account is None, what=lambda: shell.session.message)


def test_export_week_and_day_write_the_files_the_widgets_dialog_wrote(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved: dict[str, Path] = {}

    def pick(_parent, _title, name, _filter):
        saved[name] = tmp_path / name
        return str(saved[name]), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(pick))
    session = shell.session
    _open_account(qapp, shell, sheets)
    _click(shell, "exportWeek")
    week = f"flexweek-{session.week_start}.json"
    assert json.loads(saved[week].read_text()) == session.week_file()
    _open_account(qapp, shell, sheets)
    _click(shell, "exportDay")
    day = session.paste_destination()[0]
    assert json.loads(saved["flexweek-day.json"].read_text()) == session.day_file(day)


def test_export_day_with_no_day_chosen_says_so(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shell.session, "paste_destination", lambda today=None: None)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(_refuse("save dialog")))
    _open_account(qapp, shell, sheets)
    _click(shell, "exportDay")
    assert shell.session.message == "Select a day first."


def _week_file(shell: NativeWindow, tmp_path: Path) -> Path:
    path = tmp_path / "week.json"
    path.write_text(json.dumps(shell.session.week_file()))
    return path


def test_import_week_asks_before_replacing_and_only_replaces_on_the_answer(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _week_file(shell, tmp_path)
    assert json.loads(path.read_text())["format"] == EXPORT_FORMAT
    imported: list[dict] = []
    monkeypatch.setattr(
        shell.session,
        "import_week_file",
        lambda raw, replace=None: imported.append({"replace": replace}) or True,
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, "importFile")
    assert _asking(sheets) == "replace-week" and imported == []
    ask = sheets.property("ask")
    week = week_label(shell.session.week_start, shell._today())
    assert ask["title"] == "Replace week"
    assert ask["body"] == REPLACE_WEEK_QUESTION.format(week=week)
    assert ask["body"] == (
        f"Replace everything in {week} with this file? Other weeks aren't changed. You can undo this."
    )
    assert _answer_buttons(sheets) == {"stay": "Cancel", "replace": "Replace week"}
    sheets.answer("stay")
    assert imported == []
    _open_account(qapp, shell, sheets)
    _click(shell, "importFile")
    sheets.answer("replace")
    assert imported == [{"replace": True}]


def test_import_a_day_file_merges_without_asking_and_a_bad_file_says_so(
    qapp: QApplication, shell: NativeWindow, sheets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    day = tmp_path / "day.json"
    day.write_text(json.dumps(session.day_file(session.paste_destination()[0])))
    imported: list[object] = []
    monkeypatch.setattr(
        session, "import_week_file", lambda raw, replace=None: imported.append(replace) or True
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(day), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, "importFile")
    assert _asking(sheets) == "" and imported == [None]
    gone = tmp_path / "gone.json"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(gone), "")))
    _open_account(qapp, shell, sheets)
    _click(shell, "importFile")
    assert session.message == READ_WEEK_FAILED
    assert imported == [None]


def test_esc_closes_the_account_sheet_and_the_keyboard_goes_back(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _quick(shell)
    fab = _one(shell, "materialFab")
    fab.forceActiveFocus()
    pump(qapp)
    sheets.openAccount()
    pump(qapp, 40)
    assert str(quick_window_of(shell).activeFocusItem().objectName()) == "currentPasswordInput"
    _press(shell, Qt.Key.Key_Escape)
    assert _kind(sheets) == ""
    assert quick_window_of(shell).activeFocusItem() is fab


# Restore points ----------------------------------------------------------------------------------------


def _open_restore(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    sheets.openMore()
    pump(qapp, 10)
    sheets.moreAction("restoreButton")
    pump(qapp, 40)
    assert _kind(sheets) == "restore"


def _make_copy(qapp: QApplication, shell: NativeWindow, sheets, name: str) -> None:
    before = len(shell.session.restore_points)
    _type(shell, "restoreLabel", name)
    shell._material_page.bridge.sheets.setRestoreLabel(name)
    _click(shell, "restoreCreate")
    wait_until(
        qapp, lambda: len(shell.session.restore_points) == before + 1, what=lambda: shell.session.message
    )
    pump(qapp, 20)


def _labels(shell: NativeWindow) -> list[str]:
    return [
        f"{item.property('title')} · {item.property('subtitle')}"
        for item in named(_root(shell), "restorePoint")
    ]


def test_make_a_copy_lists_it_with_its_time_and_the_name_box_empties(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_restore(qapp, shell, sheets)
    assert _labels(shell) == []
    _make_copy(qapp, shell, sheets, "Before term 2")
    point = shell.session.restore_points[0]
    assert point["label"] == "Before term 2"
    # The week the seed saved is the one week the copy holds.
    assert _labels(shell) == [f"Before term 2 · {point['created_at']} · 1 week"]
    assert _text(shell, "restoreLabel") == "", "ready for the next name"
    assert shell.session.message == "Saved copy Before term 2."


def test_a_copy_needs_a_name(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _open_restore(qapp, shell, sheets)
    _click(shell, "restoreCreate")
    assert shell.session.restore_points == []
    assert _text(shell, "restoreNote") == "Name the saved copy."


def test_the_sheet_says_where_copies_are_kept(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    wait_until(qapp, lambda: shell.session.storage_info is not None)
    _open_restore(qapp, shell, sheets)
    assert _text(shell, "storageLocation") == shell.session.storage_info["label"]


def _add_block(qapp: QApplication, shell: NativeWindow, title: str) -> None:
    shell.session.add_block(
        {
            "id": "club",
            "title": title,
            "kind": "locked",
            "category": "class",
            "start": "17:00",
            "duration_min": 60,
            "days": [1],
        }
    )
    shell.session.save()
    settle(qapp, shell)


def test_preview_says_what_going_back_would_change(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _open_restore(qapp, shell, sheets)
    _make_copy(qapp, shell, sheets, "Before the club")
    sheets.forceClose()
    _add_block(qapp, shell, "Chess club")
    point_id = shell.session.restore_points[0]["id"]
    _open_restore(qapp, shell, sheets)
    # Nothing chosen: it asks for a choice.
    _click(shell, "restorePreview")
    assert _text(shell, "restoreNote") == "Choose a copy."
    _click(shell, "restorePoint")
    assert sheets.property("form")["selected"] == point_id
    _click(shell, "restorePreview")
    wait_until(qapp, lambda: shell.session.restore_preview is not None, what=lambda: shell.session.message)
    pump(qapp, 20)
    # Going back removes the one block the club added from the week, and nothing else changes.
    assert _text(shell, "restorePreviewSummary") == "0 added, 1 changed, 0 removed."


def test_restore_asks_first_and_not_now_restores_nothing(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_restore(qapp, shell, sheets)
    _make_copy(qapp, shell, sheets, "Before the club")
    applied: list[str] = []
    monkeypatch.setattr(shell.session, "apply_restore_point", applied.append)
    _click(shell, "restoreApply")
    assert _text(shell, "restoreNote") == "Choose a copy."
    assert _asking(sheets) == ""
    _click(shell, "restorePoint")
    _click(shell, "restoreApply")
    assert _asking(sheets) == "restore-copy" and applied == []
    ask = sheets.property("ask")
    assert ask["title"] == "Restore"
    assert ask["body"] == "Restore this copy? FlexWeek saves a copy of your current weeks and homework first."
    assert _answer_buttons(sheets) == {"not": "Not now", "restore": "Restore"}
    assert ask["answers"][0]["default"] is True and ask["answers"][0]["id"] == "not"
    _press(shell, Qt.Key.Key_Escape)
    assert applied == [] and _kind(sheets) == "restore"
    _click(shell, "restoreApply")
    sheets.answer("not")
    assert applied == [] and _kind(sheets) == "restore"
    _click(shell, "restoreApply")
    sheets.answer("restore")
    assert applied == [shell.session.restore_points[0]["id"]]
    assert _kind(sheets) == ""


def test_restore_goes_back_and_keeps_a_before_restore_copy_to_undo_it(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    session = shell.session
    _open_restore(qapp, shell, sheets)
    _make_copy(qapp, shell, sheets, "Before the club")
    sheets.forceClose()
    _add_block(qapp, shell, "Chess club")
    assert any(block["id"] == "club" for block in session.blocks)
    _open_restore(qapp, shell, sheets)
    _click(shell, "restorePoint")
    _click(shell, "restorePreview")
    wait_until(qapp, lambda: session.restore_preview is not None)
    pump(qapp, 20)
    _click(shell, "restoreApply")
    sheets.answer("restore")
    wait_until(qapp, lambda: session.message == "Restored.", what=lambda: session.message)
    wait_until(qapp, lambda: not session.busy)
    assert not any(block["id"] == "club" for block in session.blocks), "the week went back"
    wait_until(
        qapp,
        lambda: any(str(p["label"]).startswith("Before restore — ") for p in session.restore_points),
        what=lambda: str([p["label"] for p in session.restore_points]),
    )
    # The undo is that copy: restoring it brings the club back.
    undo = next(p for p in session.restore_points if str(p["label"]).startswith("Before restore — "))
    sheets.openRestore()
    pump(qapp, 40)
    sheets.selectRestore(str(undo["id"]))
    sheets.previewRestore()
    wait_until(qapp, lambda: (session.restore_preview or {}).get("id") == undo["id"])
    session.apply_restore_point(undo["id"])
    wait_until(
        qapp, lambda: any(block["id"] == "club" for block in session.blocks), what=lambda: session.message
    )


def test_esc_closes_the_restore_sheet_and_the_keyboard_goes_back(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _quick(shell)
    fab = _one(shell, "materialFab")
    fab.forceActiveFocus()
    pump(qapp)
    sheets.openRestore()
    pump(qapp, 40)
    assert str(quick_window_of(shell).activeFocusItem().objectName()) == "fieldInput"
    _press(shell, Qt.Key.Key_Escape)
    assert _kind(sheets) == ""
    assert quick_window_of(shell).activeFocusItem() is fab


def test_material_calls_restore_points_copies_of_this_week_in_every_student_facing_string() -> None:
    from pathlib import Path

    from desktop.native.material import bridge_manage

    material = Path(bridge_manage.__file__).parent
    qml = "\n".join(
        line
        for line in (material / "qml/sheets/RestoreSheet.qml").read_text().splitlines()
        if not line.strip().startswith("//")
    )
    words = [
        bridge_manage.RESTORE_FIRST,
        bridge_manage.RESTORE_QUESTION["body"],
        bridge_manage.restore_form([], None, None, "", "", "")["heading"],
        bridge_manage.import_question({})["body"],
        qml,
    ]
    for text in words:
        for old in ("restore point", "Restore point", "snapshot"):
            assert old not in text, f"{old!r} in {text[:60]!r}"
