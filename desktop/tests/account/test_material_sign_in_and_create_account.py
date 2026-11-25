"""Material sign in and create account, in the real window against the real backend in this process.

Expected words and values come from the Widgets cards and the requirement (what a student sees and what
the account keeps), not from reading the QML.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.setup_steps import WEEK
from desktop.native.window import NativeWindow
from desktop.tests.account.support import (
    OTHER_PASSWORD,
    WRONG_PASSWORD,
    LightLaunches,
    account,
    create,
    fill,
    light_launches,  # noqa: F401
    material_launches,  # noqa: F401
    named,
    page,
    qml,
    shown,
    sign_out,
    skip_setup,
    through_recovery,
)
from desktop.tests.light_app import _client_for
from desktop.tests.material_support import pump
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401


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
    assert bridge.recoveryStatus == "Turn on “I have saved these codes” to continue."
    bridge.setRecoveryAck(True)
    wait_until(qapp, lambda: bridge.recoveryReady)
    bridge.finishRecovery()
    wait_until(qapp, lambda: bridge.phase == "setup")
    assert bridge.setupStep == WEEK
    assert page(window) == "materialPage"
    assert shown(window, "setupFlow")
    assert qml(window, "setupTitle").property("text") == "School hours"


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


def _launch_seeing_phases(qapp: QApplication, launches: LightLaunches) -> tuple[NativeWindow, list[str]]:
    """A launch like `launches.launch()`, with every account phase recorded from the moment the window
    exists, before the kept session is tried."""
    with _client_for(launches.api):
        window = NativeWindow(launches.database, kept=launches.kept)
    seen = [account(window).phase]
    account(window).changed.connect(lambda: seen.append(account(window).phase))
    window.show()
    launches.windows.append(window)
    wait_until(qapp, lambda: not window.session.busy)
    pump(qapp, 10)
    return window, seen


def test_a_kept_session_opens_the_week_without_showing_sign_in_first(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    """Jonathan, 2026-11-24: opening FlexWeek where he was kept signed in showed the sign-in card for a
    moment before the week. While the kept session is tried, only the plain background shows."""
    first = material_launches.launch()
    create(qapp, first, "opening_student", keep=True)
    through_recovery(qapp, first)
    skip_setup(qapp, first)
    first.hide()
    second, seen = _launch_seeing_phases(qapp, material_launches)
    wait_until(qapp, lambda: account(second).phase == "app")
    assert seen[0] == "opening"
    assert "sign-in" not in seen, seen


def test_a_kept_session_that_no_longer_works_opens_on_sign_in_saying_why(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    material_launches.kept.keep("A" * 43)
    window, seen = _launch_seeing_phases(qapp, material_launches)
    assert seen[0] == "opening"
    assert account(window).phase == "sign-in"
    assert shown(window, "authCard")
    assert "sign in" in account(window).statusLine.lower()


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


def test_a_bad_load_asks_for_a_cpu_copy_instead_of_showing_the_widgets_sign_in(
    qapp: QApplication, material_launches: LightLaunches, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native import cpu_drawing
    from desktop.native.material.host import MaterialPage
    from desktop.native.version import VERSION
    from desktop.tests.window_support import look_file

    monkeypatch.delenv(cpu_drawing.BACKEND_ENV, raising=False)
    launched: list[bool] = []
    monkeypatch.setattr(cpu_drawing, "start_new_copy", lambda *, cpu: launched.append(cpu))
    monkeypatch.setattr(MaterialPage, "load", lambda self: False)
    window = material_launches.launch()
    assert launched == [True]
    assert json.loads(look_file().read_text())[cpu_drawing.LOOK_KEY] == VERSION

    # Already drawing on the CPU: the error page, never the Widgets card.
    launched.clear()
    window._material_gave_up = False
    window._relaunching = False
    monkeypatch.setenv(cpu_drawing.BACKEND_ENV, cpu_drawing.SOFTWARE)
    window._give_up_material()
    wait_until(qapp, lambda: page(window) == "drawErrorPage")
    window._show_page("authPage")
    qapp.processEvents()
    assert page(window) == "drawErrorPage"
    assert launched == []


def test_sign_in_showcase_animates_under_normal_motion_and_stays_static_under_reduce_or_off(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    from desktop.tests.material_support import focus_quick, quick_of
    from desktop.tests.window_support import look_file

    window = material_launches.launch()
    window.resize(1280, 800)
    window.activateWindow()
    focus_quick(window)
    pump(qapp, 10)
    quick = quick_of(window)
    assert quick is not None
    # Place the pointer on the form panel so a leftover Xvfb cursor at (0, 0) does not hover the showcase.
    form = qml(window, "authSurface")
    off_spot = form.mapToScene(QPointF(form.width() / 2, form.height() / 2)).toPoint()
    QTest.mouseMove(quick, off_spot)
    pump(qapp, 10)
    showcase = qml(window, "signInShowcase")
    assert showcase is not None and showcase.property("visible") is True
    assert showcase.property("staticMode") is False
    assert showcase.property("autoAdvancing") is True
    assert qml(window, "signInSlideDots").property("visible") is True

    # Finding 9: prove the timer actually advances slides, clicking a dot while hovered pauses on that
    # slide instead of restarting rotation, and hiding the showcase stops the timer.
    showcase.setProperty("slideIntervalMs", 60)
    wait_until(qapp, lambda: int(showcase.property("currentSlide")) > 0, timeout=3)

    showcase_iface = QAccessible.queryAccessibleInterface(showcase)
    assert showcase_iface is not None
    assert showcase_iface.text(QAccessible.Text.Name) == "FlexWeek preview"

    # Repeater delegates live in the visual item tree, not QObject.children(), so look them up via named().
    dot2 = named(window, "signInDot2")[0]
    assert dot2.property("activeFocusOnTab") is True
    dot2_iface = QAccessible.queryAccessibleInterface(dot2)
    assert dot2_iface is not None
    assert dot2_iface.role() == QAccessible.Role.RadioButton
    assert "Show picture 3 of 5" in dot2_iface.text(QAccessible.Text.Name)
    spot = dot2.mapToScene(QPointF(dot2.width() / 2, dot2.height() / 2)).toPoint()
    QTest.mouseMove(quick, spot)
    pump(qapp, 5)
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot)
    pump(qapp, 5)
    assert int(showcase.property("currentSlide")) == 2
    assert showcase.property("autoAdvancing") is False
    QTest.qWait(140)
    pump(qapp, 5)
    assert int(showcase.property("currentSlide")) == 2, "hovered slide must not advance after dot click"

    # Moving the pointer off the showcase onto the form resumes rotation.
    QTest.mouseMove(quick, off_spot)
    pump(qapp, 5)
    assert showcase.property("autoAdvancing") is True

    # Claude #2: indicator dots are keyboard-operable and pause rotation while focused.
    dot3 = named(window, "signInDot3")[0]
    dot3.forceActiveFocus()
    pump(qapp, 5)
    QTest.keyClick(quick, Qt.Key.Key_Space)
    pump(qapp, 5)
    assert int(showcase.property("currentSlide")) == 3
    assert showcase.property("autoAdvancing") is False
    QTest.keyClick(quick, Qt.Key.Key_Right)
    pump(qapp, 5)
    assert int(showcase.property("currentSlide")) == 4
    assert showcase.property("autoAdvancing") is False

    # Focusing password or typing into username pauses rotation; clearing and returning leaves it clean.
    pwd = qml(window, "password")
    pwd.forceActiveFocus()
    pump(qapp, 5)
    assert showcase.property("autoAdvancing") is False
    user = qml(window, "username")
    user.forceActiveFocus()
    pump(qapp, 5)
    assert showcase.property("autoAdvancing") is True
    account(window).setUsername("alex")
    pump(qapp, 5)
    assert showcase.property("autoAdvancing") is False
    account(window).setUsername("")
    pump(qapp, 5)

    # Narrowing hides the showcase and stops the timer.
    window.resize(700, 800)
    pump(qapp, 10)
    assert showcase.property("visible") is False
    assert showcase.property("autoAdvancing") is False
    window.resize(1280, 800)
    pump(qapp, 10)

    # Reduce motion and Animations Off both freeze the showcase on a single static scene.
    for motion in ("reduce", "off"):
        window._motion = motion
        window._material_page.publish()
        pump(qapp, 10)
        assert showcase.property("staticMode") is True, motion
        assert showcase.property("autoAdvancing") is False, motion
        assert int(showcase.property("currentSlide")) == 0, motion
        assert qml(window, "signInSlideDots").property("visible") is False, motion

    # Motion speed Off in the look file also stops the carousel.
    window._motion = "normal"
    look_file().write_text(json.dumps({"surface": "material", "material": {"advanced": {"motion": "Off"}}}))
    window._material_page.publish()
    pump(qapp, 10)
    assert showcase.property("staticMode") is True
    assert showcase.property("autoAdvancing") is False
