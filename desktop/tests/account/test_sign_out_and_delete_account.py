"""Sign out and Delete account ask first, and say what they will do, instead of going ahead on one
click."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native import window as window_module
from desktop.native.settings import AccountDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401


def asked_with(monkeypatch: pytest.MonkeyPatch, answer: bool) -> list[tuple[str, str, str, bool]]:
    asked: list[tuple[str, str, str, bool]] = []

    def confirm(_parent, title: str, question: str, yes: str, *, danger: bool = True) -> bool:
        asked.append((title, question, yes, danger))
        return answer

    monkeypatch.setattr(window_module, "confirm", confirm)
    return asked


SIGN_OUT = (
    "Sign out",
    "Your week is saved on this computer, under this account. Sign in again to see it.",
    "Sign out",
    False,  # Nothing is lost, so the answer is not drawn red.
)


def test_sign_out_asks_first_and_stays_signed_in_when_refused(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = asked_with(monkeypatch, False)
    window.findChild(QPushButton, "signOut").click()
    qapp.processEvents()
    assert asked == [SIGN_OUT]
    assert window.session.account is not None and window._stack.currentWidget().objectName() == "weekPage"
    asked = asked_with(monkeypatch, True)
    window.findChild(QPushButton, "signOut").click()
    wait_until(qapp, lambda: window.session.account is None)
    assert asked == [SIGN_OUT]


def open_account_and_delete(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    def run(dialog: AccountDialog) -> int:
        dialog.current_password.setText(PASSWORD)
        dialog.findChild(QPushButton, "deleteAccount").click()
        return dialog.result()

    monkeypatch.setattr(AccountDialog, "exec", run)
    window._open_account()


DELETE = (
    "Delete account",
    "Delete the account words_student? Every week, all your homework and your settings are removed "
    "from this computer. This can't be undone.",
    "Delete words_student",
    True,
)


def test_delete_account_names_the_account_and_keeps_it_when_refused(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    wait_until(qapp, lambda: window.session.storage_info is not None)
    deleted: list[str] = []
    monkeypatch.setattr(window.session, "delete_account", lambda password: deleted.append(password))
    asked = asked_with(monkeypatch, False)
    open_account_and_delete(window, monkeypatch)
    assert asked == [DELETE]
    assert deleted == []
    asked = asked_with(monkeypatch, True)
    open_account_and_delete(window, monkeypatch)
    assert asked == [DELETE]
    assert deleted == [PASSWORD]
