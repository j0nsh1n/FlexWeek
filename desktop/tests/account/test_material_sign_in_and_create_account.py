"""Material sign in and create account, in the real window against the real backend in this process.

Expected words and values come from the Widgets cards and the requirement (what a student sees and what
the account keeps), not from reading the QML.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.setup import STYLE
from desktop.tests.account.support import (
    OTHER_PASSWORD,
    WRONG_PASSWORD,
    LightLaunches,
    account,
    create,
    fill,
    light_launches,  # noqa: F401
    material_launches,  # noqa: F401
    page,
    qml,
    shown,
    sign_out,
    skip_setup,
    through_recovery,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401


def test_widgets_surface_keeps_the_widgets_sign_in(qapp: QApplication, light_launches: LightLaunches) -> None:
    window = light_launches.launch()
    assert page(window) == "authPage"
    assert window._material_page is None


def test_material_surface_opens_on_the_material_sign_in(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    assert page(window) == "materialPage"
    bridge = account(window)
    assert bridge.phase == "sign-in"
    assert bridge.heading == "Sign in"
    assert qml(window, "authCard") is not None
    assert qml(window, "authHeading").property("text") == "Sign in"
    for name in ("username", "password", "keepSignedIn", "signIn", "forgotPassword", "authSwitch"):
        assert shown(window, name), name
    assert qml(window, "authSwitch").property("text") == "New here? Create an account"
    assert bridge.statusLine == ""
    # The week behind the card is not on screen.
    assert not shown(window, "materialRail")


def test_keep_me_signed_in_starts_on_and_follows_the_switch(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    assert bridge.keepSignedIn is True
    assert qml(window, "keepSignedIn").property("checked") is True
    bridge.setKeepSignedIn(False)
    wait_until(qapp, lambda: qml(window, "keepSignedIn").property("checked") is False)
    assert window.session.keep_signed_in is False


def test_empty_fields_say_what_is_missing_before_asking_the_server(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    bridge.submit()
    assert bridge.usernameProblem == "Type your username."
    bridge.setUsername("sam")
    bridge.submit()
    assert bridge.passwordProblem == "Type your password."
    assert not window.session.busy
    wait_until(qapp, lambda: qml(window, "passwordSupport").property("text") == "Type your password.")


def test_create_account_validates_then_shows_the_codes_then_setup(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    bridge.showCreate()
    assert bridge.heading == "Create your account"
    assert bridge.passwordHint == "At least 12 characters."
    fill(window, "new_student", "short")
    bridge.submit()
    assert bridge.passwordProblem == "Add 7 more characters. Passwords need at least 12."
    assert window.session.account is None
    fill(window, "new_student")
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "recovery")
    codes = bridge.codes
    assert len(codes) >= 2 and all(codes)
    assert page(window) == "materialPage"
    wait_until(qapp, lambda: qml(window, "recoveryList").property("text") == "\n".join(codes))
    # Continue waits for the box.
    assert bridge.recoveryReady is False
    bridge.finishRecovery()
    assert bridge.phase == "recovery"
    assert bridge.recoveryStatus == "Tick the box above to continue."
    bridge.setRecoveryAck(True)
    wait_until(qapp, lambda: bridge.recoveryReady)
    bridge.finishRecovery()
    wait_until(qapp, lambda: bridge.phase == "setup")
    assert bridge.setupStep == STYLE
    assert page(window) == "materialPage"
    assert shown(window, "setupFlow")
    assert qml(window, "setupTitle").property("text") == "Start from a style"


def test_wrong_password_names_neither_field_and_explains_why(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "careful_student")
    through_recovery(qapp, window)
    skip_setup(qapp, window)
    sign_out(qapp, window)
    assert bridge.username == "" and bridge.password == ""
    fill(window, "careful_student", WRONG_PASSWORD)
    bridge.submit()
    wait_until(qapp, lambda: bridge.passwordProblem != "")
    assert bridge.passwordProblem.startswith("Wrong username or password")
    assert bridge.phase == "sign-in"
    assert window.session.account is None
    assert bridge.whyVisible is True
    wait_until(qapp, lambda: qml(window, "passwordSupport").property("text") == bridge.passwordProblem)
    bridge.explainWhy()
    wait_until(qapp, lambda: bridge.whyOpen is True)
    # Typing again takes the explanation and the red line away.
    bridge.setPassword(PASSWORD)
    assert bridge.passwordProblem == "" and bridge.whyOpen is False
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "app")
    assert window.session.account["username"] == "careful_student"


def test_forgot_password_resets_with_a_recovery_code(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    codes = create(qapp, window, "forgetful_student")
    through_recovery(qapp, window)
    skip_setup(qapp, window)
    sign_out(qapp, window)
    bridge.showReset()
    assert bridge.heading == "Reset your password"
    bridge.setUsername("forgetful_student")
    bridge.submit()
    assert bridge.recoveryProblem == "Type a recovery code."
    bridge.setRecoveryCode(codes[0])
    bridge.setNewPassword("short")
    bridge.submit()
    assert bridge.newPasswordProblem == "Add 7 more characters. Passwords need at least 12."
    bridge.setNewPassword(OTHER_PASSWORD)
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "app")
    assert window.session.account["username"] == "forgetful_student"
    # The new password is the one that works now.
    sign_out(qapp, window)
    fill(window, "forgetful_student", OTHER_PASSWORD)
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "app")
    assert page(window) == "materialPage"


def test_a_kept_session_resumes_into_the_material_week(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    first = material_launches.launch()
    create(qapp, first, "resuming_student", keep=True)
    through_recovery(qapp, first)
    skip_setup(qapp, first)
    first.hide()
    second = material_launches.launch()
    wait_until(qapp, lambda: second.session.account is not None and not second.session.busy)
    wait_until(qapp, lambda: account(second).phase == "app")
    assert page(second) == "materialPage"
    assert second.session.account["username"] == "resuming_student"
    assert shown(second, "materialRail")
    assert not shown(second, "authCard")


def test_without_keep_a_new_launch_asks_to_sign_in(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    first = material_launches.launch()
    create(qapp, first, "private_student", keep=False)
    through_recovery(qapp, first)
    skip_setup(qapp, first)
    first.hide()
    second = material_launches.launch()
    wait_until(qapp, lambda: not second.session.busy)
    assert second.session.account is None
    assert account(second).phase == "sign-in"


def test_a_bad_load_falls_back_to_the_widgets_sign_in(
    qapp: QApplication, material_launches: LightLaunches, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native.material.host import MaterialPage

    monkeypatch.setattr(MaterialPage, "load", lambda self: False)
    window = material_launches.launch()
    assert page(window) == "authPage"
    assert window._material_gave_up is True
    # The Widgets card still works.
    window.username.setText("fallback_student")
    window.password.setText(PASSWORD)
    window.create_button.click()
    wait_until(qapp, lambda: page(window) == "recoveryPage")
