"""Material sign in, account and first-run setup, in the real window against a real local backend.

Expected words and values come from the Widgets pages and the requirement (what a student sees and what
the account keeps), not from reading the QML.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.kept import KeptSession  # noqa: E402
from desktop.native.setup import COLOURS, DONE, FIRST, HOMEWORK, LOOK, REMINDERS, STYLE, WEEK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.server import LocalServer  # noqa: E402

PASSWORD = "a-long-test-password"
OTHER_PASSWORD = "another-long-password"
WRONG_PASSWORD = "not-the-right-password"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-account-test"])
    yield application


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


class Launches:
    """Launches of the app against one database, each with its own server and kept-session file."""

    def __init__(self, qapp: QApplication, folder: Path) -> None:
        self.qapp = qapp
        self.database = folder / "flexweek.db"
        self.kept = KeptSession(folder / "signed-in" / "flexweek.json")
        self.servers: list[LocalServer] = []
        self.windows: list[NativeWindow] = []

    def launch(self) -> NativeWindow:
        server = LocalServer(self.database)
        origin = server.start()
        self.servers.append(server)
        window = NativeWindow(origin, kept=self.kept)
        window.resize(1280, 800)
        window.show()
        self.windows.append(window)
        for _ in range(40):
            self.qapp.processEvents()
        return window

    def close(self) -> None:
        for window in self.windows:
            window.hide()
        for server in self.servers:
            with contextlib.suppress(Exception):
                server.stop()


@pytest.fixture()
def launches(qapp: QApplication, tmp_path: Path) -> Iterator[Launches]:
    """Material is the saved surface on this computer."""
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps({"surface": "material"}) + "\n")
    made = Launches(qapp, tmp_path)
    yield made
    made.close()
    look_file().unlink(missing_ok=True)


def account(window: NativeWindow):
    bridge = window._account_bridge()
    assert bridge is not None
    return bridge


def page(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


def root_of(window: NativeWindow) -> QObject:
    root = window._material_page.root
    assert root is not None
    return root


def qml(window: NativeWindow, name: str) -> QObject:
    found = root_of(window).findChild(QObject, name)
    assert found is not None, name
    return found


def visuals(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(visuals(child))
    return found


def named(window: NativeWindow, name: str) -> list[QObject]:
    return [item for item in visuals(root_of(window)) if str(item.objectName()) == name]


def shown(window: NativeWindow, name: str) -> bool:
    """A named QML item that is on screen, including through a hidden parent."""
    for item in named(window, name):
        if hasattr(item, "isVisible"):
            if item.isVisible():
                return True
            continue
        if bool(item.property("visible")):
            return True
    return False


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def fill(window: NativeWindow, name: str, password: str = PASSWORD) -> None:
    bridge = account(window)
    bridge.setUsername(name)
    bridge.setPassword(password)


def create(qapp: QApplication, window: NativeWindow, name: str, *, keep: bool = True) -> list[str]:
    """Register on the Material card and stop on the recovery codes. Returns the codes."""
    bridge = account(window)
    bridge.showCreate()
    fill(window, name)
    bridge.setKeepSignedIn(keep)
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "recovery")
    return bridge.codes


def through_recovery(qapp: QApplication, window: NativeWindow) -> None:
    bridge = account(window)
    bridge.setRecoveryAck(True)
    wait_until(qapp, lambda: bridge.recoveryReady)
    bridge.finishRecovery()
    wait_until(qapp, lambda: bridge.phase == "setup")


def settle(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    wait_until(
        qapp,
        lambda: not session.busy
        and not session.setup_prefs
        and session.setup_work_windows is None
        and not session.setup_week,
    )
    pump(qapp)


def skip_setup(qapp: QApplication, window: NativeWindow) -> None:
    bridge = account(window)
    bridge.setupSkipAll()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)


def sign_out(qapp: QApplication, window: NativeWindow) -> None:
    window.session.logout()
    wait_until(qapp, lambda: account(window).phase == "sign-in" and window.session.account is None)


def test_widgets_surface_keeps_the_widgets_sign_in(qapp: QApplication, tmp_path: Path) -> None:
    look_file().unlink(missing_ok=True)
    made = Launches(qapp, tmp_path)
    try:
        window = made.launch()
        assert page(window) == "authPage"
        assert window._material_page is None
    finally:
        made.close()


def test_material_surface_opens_on_the_material_sign_in(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
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


def test_keep_me_signed_in_starts_on_and_follows_the_switch(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
    bridge = account(window)
    assert bridge.keepSignedIn is True
    assert qml(window, "keepSignedIn").property("checked") is True
    bridge.setKeepSignedIn(False)
    pump(qapp)
    assert window.session.keep_signed_in is False
    assert qml(window, "keepSignedIn").property("checked") is False


def test_empty_fields_say_what_is_missing_before_asking_the_server(
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
    bridge = account(window)
    bridge.submit()
    assert bridge.usernameProblem == "Type your username."
    bridge.setUsername("sam")
    bridge.submit()
    assert bridge.passwordProblem == "Type your password."
    assert not window.session.busy
    pump(qapp)
    assert qml(window, "passwordSupport").property("text") == "Type your password."


def test_create_account_validates_then_shows_the_codes_then_setup(
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
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
    assert qml(window, "recoveryList").property("text") == "\n".join(codes)
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
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
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
    pump(qapp)
    assert qml(window, "passwordSupport").property("text") == bridge.passwordProblem
    bridge.explainWhy()
    pump(qapp)
    assert bridge.whyOpen is True
    # Typing again takes the explanation and the red line away.
    bridge.setPassword(PASSWORD)
    assert bridge.passwordProblem == "" and bridge.whyOpen is False
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "app")
    assert window.session.account["username"] == "careful_student"


def test_forgot_password_resets_with_a_recovery_code(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
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


def test_a_kept_session_resumes_into_the_material_week(qapp: QApplication, launches: Launches) -> None:
    first = launches.launch()
    create(qapp, first, "resuming_student", keep=True)
    through_recovery(qapp, first)
    skip_setup(qapp, first)
    first.hide()
    second = launches.launch()
    wait_until(qapp, lambda: second.session.account is not None and not second.session.busy)
    wait_until(qapp, lambda: account(second).phase == "app")
    assert page(second) == "materialPage"
    assert second.session.account["username"] == "resuming_student"
    assert shown(second, "materialRail")
    assert not shown(second, "authCard")


def test_without_keep_a_new_launch_asks_to_sign_in(qapp: QApplication, launches: Launches) -> None:
    first = launches.launch()
    create(qapp, first, "private_student", keep=False)
    through_recovery(qapp, first)
    skip_setup(qapp, first)
    first.hide()
    second = launches.launch()
    wait_until(qapp, lambda: not second.session.busy)
    assert second.session.account is None
    assert account(second).phase == "sign-in"


def test_setup_keeps_each_step_in_order_and_what_was_answered(
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
    bridge = account(window)
    create(qapp, window, "setup_student")
    through_recovery(qapp, window)
    session = window.session
    # The style step offers Material 3 first, then the four standard styles.
    keys = [row["key"] for row in bridge.styles]
    assert keys[0] == "material"
    assert len(keys) == 5
    assert [row["selected"] for row in bridge.styles][0] is True
    seen = [bridge.setupStep]

    def step_saved(step: int) -> bool:
        wanted = (session.preferences or {}).get("setup", {}).get("step")
        return wanted == step

    # Style -> Your week
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(WEEK))
    bridge.setClock24(True)
    bridge.setCutoff("21:00")
    bridge.toggleSchoolDay(5)
    assert 5 in bridge.schoolDays
    bridge.toggleSchoolDay(5)
    bridge.setActivityTitle(0, "Soccer")
    bridge.toggleActivityDay(0, 1)
    bridge.toggleActivityDay(0, 3)
    bridge.setActivityStart(0, "4:00 pm")
    bridge.setActivityEnd(0, "17:30")
    assert bridge.activities[0]["category"] == "exercise"
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(HOMEWORK))
    assert session.preferences["day_cutoff"] == "21:00"
    assert session.preferences["clock_24h"] is True
    soccer = next(block for block in session.blocks if block["title"] == "Soccer")
    assert soccer["days"] == [1, 3] and soccer["start"] == "16:00" and soccer["duration_min"] == 90
    # Homework time
    bridge.setPlanning("manual")
    bridge.setDragStep(15)
    bridge.addWorkPreset("After school")
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(REMINDERS))
    assert session.preferences["planning_style"] == "manual"
    assert session.preferences["drag_step_min"] == 15
    settle(qapp, window)
    assert session.preferences["work_windows"][0]["start"] == "15:30"
    # Reminders
    bridge.setReminders(True)
    bridge.setLead(20)
    tone = next(row["value"] for row in bridge.tones if row["value"] != "spotify")
    bridge.setTone(tone)
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(FIRST))
    assert session.preferences["reminder_lead_min"] == 20
    assert session.preferences["alarm_tone"] == tone
    # First homework
    bridge.setHomeworkTitle(0, "Chemistry lab")
    bridge.setHomeworkMinutes(0, 45)
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(DONE))
    assert seen == [STYLE, WEEK, HOMEWORK, REMINDERS, FIRST, DONE]
    assert any(item["title"] == "Chemistry lab" for item in session.assignments.values())
    assert "Chemistry lab" in " ".join(row["value"] for row in bridge.summaryRows)
    assert bridge.summaryRows[0]["value"] == "Material 3"
    assert bridge.nextLabel == "Open my week"
    # Finish: the Material week opens.
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    assert page(window) == "materialPage"
    assert shown(window, "materialRail")
    assert (session.preferences.get("setup") or {}).get("finished_at")
    assert window._surface == "material"


def test_picking_a_standard_style_hands_the_window_to_widgets_when_setup_ends(
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
    bridge = account(window)
    create(qapp, window, "plain_student")
    through_recovery(qapp, window)
    plain = next(row["key"] for row in bridge.styles if row["key"] != "material")
    bridge.chooseStyle(plain)
    bridge.setupNext()
    assert window._surface == "material"  # not yet: setup is still on screen
    bridge.setupSkipAll()
    wait_until(qapp, lambda: window._surface == "widgets")
    settle(qapp, window)
    assert page(window) == "weekPage"
    assert json.loads(look_file().read_text())["surface"] == "widgets"


def test_a_second_account_does_not_inherit_the_first_ones_answers(
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
    bridge = account(window)
    create(qapp, window, "first_student")
    through_recovery(qapp, window)
    bridge.setupNext()
    bridge.setCutoff("20:00")
    bridge.setActivityTitle(0, "Robotics club")
    bridge.toggleActivityDay(0, 2)
    bridge.setupNext()
    bridge.setupNext()
    bridge.setupNext()
    bridge.setHomeworkTitle(0, "Essay for first")
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == DONE)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    sign_out(qapp, window)
    assert bridge.username == "" and bridge.password == ""
    create(qapp, window, "second_student")
    through_recovery(qapp, window)
    assert bridge.setupStep == STYLE
    assert [row["selected"] for row in bridge.styles][0] is True
    bridge.setupNext()
    assert bridge.setupStep == WEEK
    assert bridge.cutoff == ""
    assert bridge.activities == [
        {"title": "", "days": [], "start": "3:30 PM", "end": "5:00 PM", "category": "extra"}
    ]
    for _ in range(3):
        bridge.setupNext()
    assert bridge.setupStep == FIRST
    assert [row["title"] for row in bridge.homeworkRows] == [""]
    assert not any(block["title"] == "Robotics club" for block in window.session.blocks)


def test_a_time_that_ends_before_it_starts_stops_the_week_step(
    qapp: QApplication, launches: Launches
) -> None:
    window = launches.launch()
    bridge = account(window)
    create(qapp, window, "clock_student")
    through_recovery(qapp, window)
    bridge.setupNext()
    bridge.setSchoolStart("2:00 pm")
    bridge.setSchoolEnd("8:00 am")
    bridge.setupNext()
    assert bridge.setupStep == WEEK
    assert bridge.setupProblem == "School has to end after it starts."
    pump(qapp)
    assert qml(window, "setupProblem").property("text") == "School has to end after it starts."
    bridge.setSchoolEnd("4:00 pm")
    bridge.setupNext()
    assert bridge.setupStep == HOMEWORK


def test_an_own_look_adds_the_look_and_colour_pages(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
    bridge = account(window)
    create(qapp, window, "look_student")
    through_recovery(qapp, window)
    bridge.chooseOwnLook()
    assert bridge.setupStep == LOOK
    assert len(bridge.mains) >= 2
    bridge.setupNext()
    assert bridge.setupStep == COLOURS
    assert [row["key"] for row in bridge.knobRows][:2] == ["text", "density"]
    bridge.setupBack()
    assert bridge.setupStep == LOOK


def test_setup_keeps_the_computers_material_mode(qapp: QApplication, launches: Launches) -> None:
    look_file().write_text(json.dumps({"surface": "material", "material": {"mode": "dark"}}) + "\n")
    window = launches.launch()
    create(qapp, window, "dark_mode_student")
    through_recovery(qapp, window)
    skip_setup(qapp, window)
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored["material"]["mode"] == "dark"
    assert account(window).phase == "app"
    assert window._material_page.bridge.dark is True


def test_a_bad_load_falls_back_to_the_widgets_sign_in(
    qapp: QApplication, launches: Launches, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native.material.host import MaterialPage

    monkeypatch.setattr(MaterialPage, "load", lambda self: False)
    window = launches.launch()
    assert page(window) == "authPage"
    assert window._material_gave_up is True
    # The Widgets card still works.
    window.username.setText("fallback_student")
    window.password.setText(PASSWORD)
    window.create_button.click()
    wait_until(qapp, lambda: page(window) == "recoveryPage")
