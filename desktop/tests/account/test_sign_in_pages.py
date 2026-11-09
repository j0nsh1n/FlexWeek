"""The sign-in card's behaviour: one heading, which links and buttons each page shows, hints under their
own field, a wrong sign-in said on the password line, the eye that shows and hides the password, and
links that answer the pointer and the keyboard. How the card looks is in the sign-in screens
(desktop/tests/pictures/screens_account_signin.py)."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QPushButton

from desktop.native.client import SIGN_IN_WRONG, TOO_MANY_TRIES
from desktop.native.window import CREATE_NOTE, NativeWindow
from desktop.tests.account.support_signin import (  # noqa: F401
    MODES,
    Computer,
    card_of,
    computer,
    go,
    page,
    pump,
    shown,
    signed_out,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, qapp  # noqa: F401

# One heading.


def test_the_heading_is_sign_in_on_a_first_launch_and_on_a_return(qapp, computer: Computer) -> None:
    window = computer.launch()
    assert window.auth_heading.text() == "Sign in"
    computer.reach_recovery(window, USERNAME, keep=True)
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(qapp, lambda: not window.session.busy)
    window.session.logout()
    wait_until(qapp, lambda: page(window) == "authPage" and not window.session.busy)
    assert computer.kept.signed_in_before(), "Log out forgets the session, not that someone was here"
    assert window.auth_heading.text() == "Sign in"
    again = computer.relaunch(window)
    assert computer.kept.signed_in_before()
    assert again.auth_heading.text() == "Sign in"


def test_the_card_has_one_heading_and_create_account_hides_forgot_password(
    signed_out: NativeWindow,
) -> None:
    window = signed_out
    assert window.auth_heading.text() == "Sign in"
    assert not window.auth_note.isVisibleTo(window), "no second heading under the first"
    assert shown(window, "forgotPassword")
    window.auth_switch.click()
    assert window.auth_heading.text() == "Create your account"
    assert window.auth_note.isVisibleTo(window)
    assert window.auth_note.text() == CREATE_NOTE
    assert window.auth_note.text() == (
        "FlexWeek fits homework around school and sports. "
        "Your week is saved on this computer, under this account. "
        "Export a backup file now and then (Settings > This computer > Manage account)."
    )
    assert not shown(window, "forgotPassword"), "a new account has no password to forget"
    window.auth_switch.click()
    assert shown(window, "forgotPassword")


def test_the_name_is_said_once_not_again_in_the_heading(signed_out: NativeWindow) -> None:
    """The wordmark sat right above "Welcome to FlexWeek"."""
    window = signed_out
    stage = window._stack.currentWidget()
    for mode in MODES:
        go(window, mode)
        assert "FlexWeek" not in window.auth_heading.text(), (mode, window.auth_heading.text())
        marks = [label for label in stage.findChildren(QLabel) if label.text() == "FlexWeek"]
        assert [label.objectName() for label in marks] == ["authBrand"], mode


def test_the_wordmark_is_on_the_page_not_in_the_card(signed_out: NativeWindow) -> None:
    held = card_of(signed_out)
    stage = signed_out._stack.currentWidget()
    brand = stage.findChild(QLabel, "authBrand")
    logo = stage.findChild(QLabel, "authLogo")
    assert brand is not None and logo is not None, "the sign-in page has no wordmark and logo"
    assert brand.text() == "FlexWeek"
    assert not held.isAncestorOf(brand), "the wordmark is on the page, not in the card"
    assert not held.isAncestorOf(logo)


# What each page shows.


def test_forgot_password_is_the_cards_own_page_with_one_filled_button(signed_out: NativeWindow) -> None:
    """It opened a second form under Sign in: two filled buttons and two passwords at once."""
    window = signed_out
    window.findChild(QPushButton, "forgotPassword").click()
    assert window.auth_heading.text() == "Reset your password"
    answers = [name for name in ("signIn", "createAccount", "recoverAccount") if shown(window, name)]
    assert answers == ["recoverAccount"]
    assert not window.password.isVisibleTo(window), "only the new password is asked for"
    assert window.recovery_code.isVisibleTo(window) and window.new_recovery_password.isVisibleTo(window)
    assert not shown(window, "forgotPassword")
    assert window.auth_switch.text() == "Back to sign in"
    window.auth_switch.click()
    assert window.auth_heading.text() == "Sign in"
    assert [name for name in ("signIn", "createAccount", "recoverAccount") if shown(window, name)] == [
        "signIn"
    ]
    assert not window.recovery_code.isVisibleTo(window)


def test_sign_in_offers_both_forgot_password_and_create_an_account(signed_out: NativeWindow) -> None:
    window = signed_out
    assert shown(window, "forgotPassword") and shown(window, "authSwitch")
    assert window.auth_switch.text() == "New here? Create an account"


# Hints.


def test_a_hint_sits_under_its_own_field_and_only_on_the_create_page(signed_out: NativeWindow) -> None:
    window = signed_out
    go(window, "sign in")
    assert not window.username_hint.isVisibleTo(window)
    assert not window.password_hint.isVisibleTo(window)
    go(window, "create")
    held = card_of(window)

    def top(widget: QLabel | QLineEdit | QCheckBox) -> int:
        return widget.mapTo(held, QPoint(0, 0)).y()

    def bottom(widget: QLabel | QLineEdit | QCheckBox) -> int:
        return top(widget) + widget.height()

    assert window.username_hint.isVisibleTo(window) and window.password_hint.isVisibleTo(window)
    assert top(window.username_hint) >= bottom(window.username)
    # The Password caption sits above its field, so the next thing after the username's hint is that caption.
    assert top(window.password_caption) >= bottom(window.username_hint)
    assert top(window.password_hint) >= bottom(window.password)
    assert top(window.keep_signed_in) >= bottom(window.password_hint)


# What is said when sign-in fails.


def test_a_wrong_sign_in_is_said_on_the_password_line_and_announced(
    signed_out: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = signed_out
    announced = []
    monkeypatch.setattr(
        "desktop.native.window.announce",
        lambda field, words, assertive=False: announced.append((field, words, assertive)),
    )
    window._on_status(SIGN_IN_WRONG)
    pump()
    line = window.password_problem
    assert line.isVisibleTo(window)
    assert line.text.text() == SIGN_IN_WRONG
    assert not window.auth_status.isVisibleTo(window), "the long sentence is not also at the foot"
    assert not line.icon.pixmap().isNull(), "the error mark is drawn beside the words"
    assert window.password.accessibleDescription() == line.text.text()
    assert announced == [(window.password, f"Error: {line.text.text()}", True)]


def test_a_field_problem_is_the_only_error_for_its_field(signed_out: NativeWindow) -> None:
    """The old box under Password and the foot line never show beside the line under the field."""
    window = signed_out
    window._on_status(SIGN_IN_WRONG)
    pump()
    assert window.password_problem.isVisibleTo(window)
    assert not window.auth_error.isVisibleTo(window)
    assert not window.auth_status.isVisibleTo(window)


def test_too_many_tries_is_shown_under_its_field(signed_out: NativeWindow) -> None:
    window = signed_out
    go(window, "sign in")
    window.session._say(TOO_MANY_TRIES)
    pump()
    assert window.password_problem.text.text() == TOO_MANY_TRIES
    assert window.password_problem.isVisibleTo(window)
    assert window.password.hasFocus()
    assert window.auth_status.text() == ""
    go(window, "reset")
    window.session._say(TOO_MANY_TRIES)
    pump()
    assert window.recovery_code_problem.text.text() == TOO_MANY_TRIES
    assert window.recovery_code.hasFocus()


# The eye.


def test_the_eye_shows_and_hides_the_password_and_a_log_out_hides_it_again(signed_out: NativeWindow) -> None:
    window = signed_out
    eye = window.password_reveal
    assert eye.parentWidget() is window.password, "the eye is inside the password box"
    assert window.password.echoMode() == QLineEdit.EchoMode.Password
    assert eye.toolTip() == "Show password"
    assert eye.accessibleName() == "Show password"
    window.password.setText("a-long-test-password")
    eye.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(eye, Qt.Key.Key_Space)
    assert window.password.echoMode() == QLineEdit.EchoMode.Normal, "the keyboard shows it too"
    assert eye.toolTip() == "Hide password"
    assert eye.accessibleName() == "Hide password"
    eye.click()
    assert window.password.echoMode() == QLineEdit.EchoMode.Password, "a click hides it again"
    eye.click()
    assert window.password.echoMode() == QLineEdit.EchoMode.Normal
    window._on_account(None)
    assert window.password.echoMode() == QLineEdit.EchoMode.Password, "a log out hides it again"
    assert eye.toolTip() == "Show password"


def test_a_log_out_hides_a_shown_password_and_empties_the_box(qapp, computer: Computer) -> None:
    window = computer.launch()
    computer.create_account(window, "shared_one")
    window.password.setText(PASSWORD)
    window.password_reveal.setChecked(True)
    computer.sign_out(window)
    assert window.password_reveal.isChecked() is False
    assert window.password.echoMode() == QLineEdit.EchoMode.Password
    assert window.password.text() == "", "the password is not left in the box"


# Links answer the pointer and the keyboard.


@pytest.mark.parametrize("name", ["forgotPassword", "authSwitch"])
def test_the_pointer_over_a_sign_in_link_hovers_it(signed_out: NativeWindow, name: str) -> None:
    link = signed_out.findChild(QPushButton, name)
    assert not link.underMouse()
    QTest.mouseMove(link, QPoint(link.width() // 2, link.height() // 2))
    wait_until(None, link.underMouse, what=f"the pointer over {name}")


@pytest.mark.parametrize("name", ["forgotPassword", "authSwitch"])
def test_a_sign_in_link_reached_by_the_keyboard_is_marked(signed_out: NativeWindow, name: str) -> None:
    window = signed_out
    link = window.findChild(QPushButton, name)
    window.activateWindow()
    wait_until(None, window.isActiveWindow, what="the window becoming active")
    link.setFocus(Qt.FocusReason.TabFocusReason)
    wait_until(None, lambda: bool(link.property("keyfocus")), what=f"{name} marked as keyboard-reached")
