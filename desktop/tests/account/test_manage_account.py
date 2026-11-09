"""The Account dialog: where the plans are saved, how many recovery codes are left, the Show password
eyes, and the words after saving a backup file or refusing an export or import."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QToolButton

from desktop.native import window as window_module
from desktop.native.settings import AccountDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_account_says_where_the_plans_are_saved_in_a_sentence(
    qapp: QApplication, window: NativeWindow
) -> None:
    wait_until(qapp, lambda: window.session.storage_info is not None)
    dialog = AccountDialog(window, window.session.recovery_remaining, window.session.storage_info)
    assert dialog.findChild(QLabel, "accountLocation").text() == (
        "Signed in as words_student. Your week is saved on this computer, under this account."
    )
    dialog.close()


@pytest.mark.parametrize(
    ("remaining", "said", "is_a_problem"),
    [
        (8, "8 unused recovery codes remain.", False),
        (1, "1 unused recovery code remains.", False),
        (0, "No unused recovery codes remain. Replace them before signing out.", True),
        (None, "Recovery-code status unavailable.", False),
    ],
)
def test_the_recovery_codes_left_are_a_problem_only_when_there_are_none(
    qapp: QApplication, window: NativeWindow, remaining: int | None, said: str, is_a_problem: bool
) -> None:
    """Codes left are an ordinary fact until there are none (decision 8 of 0.17: red is for a problem).
    How the two are drawn is the picture account.manage_account's."""
    dialog = AccountDialog(window, remaining, {"username": "student"})
    label = dialog.findChild(QLabel, "recoveryCount")
    assert label.text() == said
    assert label.property("problem") is is_a_problem
    dialog.close()


def test_manage_account_password_boxes_have_the_eye_sign_in_has(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Both boxes hold a Show password eye that flips the echo between dots and the typed text."""
    dialog = AccountDialog(window, 8, {"username": "student"})
    dialog.show()
    qapp.processEvents()
    for field in (dialog.current_password, dialog.new_password):
        eye = field.findChild(QToolButton, "passwordReveal")
        assert eye is not None and eye.isVisible()
        assert field.echoMode() == QLineEdit.EchoMode.Password
        assert eye.accessibleName() == "Show password"
        eye.click()
        assert field.echoMode() == QLineEdit.EchoMode.Normal
        assert eye.accessibleName() == "Hide password"
        eye.click()
        assert field.echoMode() == QLineEdit.EchoMode.Password
    dialog.close()


def test_a_backup_file_says_where_it_was_saved(
    qapp: QApplication, window: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "flexweek-account-joo.json"
    picked = (str(target), "")
    monkeypatch.setattr(window_module.QFileDialog, "getSaveFileName", lambda *args, **kwargs: picked)
    window._write_account_file({"username": "joo"})
    assert target.is_file()
    assert window.session.message == (
        f"Saved your backup file to {target}. Keep it private: it has all your weeks and homework."
    )


def test_export_and_import_refusals_say_to_save_first_with_retry(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    session.dirty = True
    session.export_account("unused", lambda data: None)
    assert session.message == "Save your last change first (More > Retry save), then export."
    session.preview_account_import({"username": "joo"})
    assert session.message == "Save your last change first (More > Retry save), then import."
