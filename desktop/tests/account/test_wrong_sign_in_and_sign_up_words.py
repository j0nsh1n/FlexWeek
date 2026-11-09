"""Signing in and signing up say what went wrong in words, and a message does not follow the student
onto the next card.

Sign-in used to say "Check the required fields, dates, times and lengths" for an empty password, a
short one and a mistyped username alike. Sign-up repeated the hint already on screen for an empty
password, so nothing seemed to happen.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, qapp  # noqa: F401

WRONG = "Wrong username or password. Try again, or choose Forgot password."


def press(qapp: QApplication, window: NativeWindow, name: str, username: str, password: str) -> str:
    """Fill the card, press the button `name` and return the words the card ends up showing."""
    wanted = window.findChild(QPushButton, name)
    if wanted.isHidden():
        window.findChild(QPushButton, "authSwitch").click()
    window.username.setText(username)
    window.password.setText(password)
    window.session._say("")
    wanted.click()

    def said() -> str:
        return (
            window.auth_status.text()
            or window.username_problem.text.text()
            or window.password_problem.text.text()
        )

    wait_until(qapp, lambda: not window.session.busy and bool(said()))
    return said()


@pytest.fixture()
def returning(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    """An account exists and has signed out, so the next person at the window signs in."""
    window.session.logout()
    wait_until(qapp, lambda: window.session.account is None and not window.session.busy)
    return window


@pytest.mark.parametrize(
    ("username", "password", "said"),
    [
        ("", PASSWORD, "Type your username."),
        (USERNAME, "", "Type your password."),
        (USERNAME, "not-the-right-password", WRONG),
        ("nobody_by_this_name", PASSWORD, WRONG),
        (
            USERNAME,
            "short",
            "That isn't your password. FlexWeek passwords have at least 12 characters.",
        ),
        (
            "has spaces",
            PASSWORD,
            "No FlexWeek username looks like that. Usernames are 3–32 letters, numbers or underscores.",
        ),
    ],
)
def test_sign_in_says_what_went_wrong(
    qapp: QApplication, returning: NativeWindow, username: str, password: str, said: str
) -> None:
    assert press(qapp, returning, "signIn", username, password) == said
    assert returning.session.account is None


@pytest.mark.parametrize(
    ("username", "password", "said"),
    [
        ("new_student", "", "Choose a password with at least 12 characters."),
        ("new_student", "short", "Add 7 more characters. Passwords need at least 12."),
        ("", PASSWORD, "Choose a username."),
        (USERNAME, PASSWORD, "That username is taken. Try another."),
    ],
)
def test_sign_up_says_what_went_wrong(
    qapp: QApplication, returning: NativeWindow, username: str, password: str, said: str
) -> None:
    assert press(qapp, returning, "createAccount", username, password) == said
    assert returning.session.account is None


def test_a_sign_in_error_does_not_follow_onto_reset_your_password(
    qapp: QApplication, returning: NativeWindow
) -> None:
    press(qapp, returning, "signIn", USERNAME, "not-the-right-password")
    assert returning.password_problem.isVisibleTo(returning)
    returning.findChild(QPushButton, "forgotPassword").click()
    qapp.processEvents()
    assert returning.auth_heading.text() == "Reset your password"
    assert returning.auth_status.text() == ""
    assert not returning.auth_status.isVisible()
    assert not returning.password_problem.isVisibleTo(returning)


def test_signed_out_does_not_stay_on_reset_your_password(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native import window as window_module

    monkeypatch.setattr(window_module, "confirm", lambda *_args, **_kwargs: True)
    window.findChild(QPushButton, "signOut").click()
    wait_until(qapp, lambda: window.session.account is None and not window.session.busy)
    assert window.auth_status.text() == "Signed out."
    window.findChild(QPushButton, "forgotPassword").click()
    qapp.processEvents()
    assert window.auth_heading.text() == "Reset your password"
    assert window.auth_status.text() == ""
    assert not window.auth_status.isVisible()


def test_a_recovery_error_does_not_follow_back_to_sign_in(
    qapp: QApplication, returning: NativeWindow
) -> None:
    returning.findChild(QPushButton, "forgotPassword").click()
    qapp.processEvents()
    returning.username.setText(USERNAME)
    returning.recovery_code.setText("not-a-code")
    returning.new_recovery_password.setText(PASSWORD)
    returning.findChild(QPushButton, "recoverAccount").click()
    wait_until(
        qapp,
        lambda: not returning.session.busy and returning.recovery_code_problem.isVisibleTo(returning),
    )
    assert returning.recovery_code_problem.text.text() == (
        "Wrong username or recovery code. Each code works once; try another one."
    )
    returning.findChild(QPushButton, "authSwitch").click()
    qapp.processEvents()
    assert returning.auth_heading.text() == "Sign in"
    assert returning.auth_status.text() == ""
    assert not returning.auth_status.isVisible()
    assert not returning.recovery_code_problem.isVisibleTo(returning)


def test_account_messages_use_the_audit_sentences(qapp: QApplication, returning: NativeWindow) -> None:
    from desktop.native.client import (
        PASSWORD_LENGTH_HINT,
        TOO_MANY_TRIES,
        USERNAME_HINT,
        WRONG_PASSWORD,
        _error,
        sign_up_problem,
    )

    assert sign_up_problem("abc", "a" * 11) == "Add 1 more character. Passwords need at least 12."
    assert sign_up_problem("abc", "a" * 10) == "Add 2 more characters. Passwords need at least 12."
    returning.findChild(QPushButton, "authSwitch").click()
    qapp.processEvents()
    assert returning.username_hint.text() == USERNAME_HINT
    assert returning.password_hint.text() == PASSWORD_LENGTH_HINT
    assert USERNAME_HINT == "3 to 32 letters, numbers or underscores."
    assert PASSWORD_LENGTH_HINT == "At least 12 characters."
    assert _error(429).message == TOO_MANY_TRIES
    assert TOO_MANY_TRIES == "Too many tries. Wait 5 minutes, then try again."
    assert _error(401, "Incorrect password").message == WRONG_PASSWORD
    assert WRONG_PASSWORD == "Wrong password. Try again."
    returning.findChild(QPushButton, "authSwitch").click()
    qapp.processEvents()
    returning.findChild(QPushButton, "forgotPassword").click()
    qapp.processEvents()
    returning.username.setText(USERNAME)
    returning.recovery_code.clear()
    returning.new_recovery_password.setText(PASSWORD)
    returning.findChild(QPushButton, "recoverAccount").click()
    qapp.processEvents()
    assert returning.recovery_code_problem.text.text() == "Type a recovery code."


def test_a_wrong_sign_in_and_an_ended_session_keep_their_own_words() -> None:
    """The server answers both with 401: a wrong password says so, and an expired session says it
    ended."""
    from backend.app import SESSION_ENDED
    from desktop.native.client import SESSION_ENDED as CLIENT_ENDED
    from desktop.native.client import SIGN_IN_WRONG, _error

    assert _error(401, "Incorrect username or password").message == SIGN_IN_WRONG
    assert _error(401, SESSION_ENDED).message == CLIENT_ENDED
    assert CLIENT_ENDED == "Your session ended. Sign in again."
