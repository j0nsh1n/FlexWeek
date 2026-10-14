"""The one-time 1.0.0 look notice belongs to existing accounts on this device."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QPushButton

    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer

PASSWORD = "a-long-test-password"
NOTICE = "New in 1.0.0: each design has its own looks."


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-new-looks-notice-test"])
    yield application


def wait_until(qapp: QApplication, predicate, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def device_look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


def make_new_account(qapp: QApplication, server: LocalServer, username: str) -> NativeWindow:
    made = NativeWindow(server.origin)
    made.show()
    made.username.setText(username)
    made.password.setText(PASSWORD)
    made.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
    made.recovery_ack.setChecked(True)
    made.recovery_continue.click()
    wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "setupPage")
    made.setup_page.skip_all.click()
    wait_until(
        qapp,
        lambda: made._stack.currentWidget().objectName() == "weekPage"
        and made.session.preferences is not None
        and not made.session.busy
        and not made._setup_prefs,
    )
    return made


@pytest.fixture()
def server(qapp: QApplication, tmp_path: Path) -> Iterator[LocalServer]:
    device_look_file().unlink(missing_ok=True)
    running = LocalServer(tmp_path / "new-looks.db")
    running.start()
    yield running
    running.stop()


@pytest.fixture()
def fresh_window(qapp: QApplication, server: LocalServer) -> Iterator[NativeWindow]:
    made = make_new_account(qapp, server, "looks_fresh")
    yield made
    made.session.client.reset()
    made.hide()
    made.close()
    qapp.processEvents()


def make_legacy_account(window: NativeWindow) -> None:
    """Model a finished pre-1.0 account whose device file has no design look choices."""
    assert window.session.preferences["setup"].get("finished_at")
    saved = json.loads(device_look_file().read_text())
    saved["layout"] = {"main": "classic", "day": "dial", "options": {}}
    saved.pop("new_look_notice_exempt", None)
    saved.pop("new_look_notice_seen", None)
    device_look_file().write_text(json.dumps(saved) + "\n")
    window.session.new_account = False
    window._load_look()


def test_an_existing_pre_100_account_sees_the_notice_once_on_its_first_planner_open(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)
    planner_geometry = window.planner.geometry()

    window._on_week()

    assert window.toast.isVisible()
    assert window.toast.text() == NOTICE
    assert window.toast.button.text() == "Choose a look"
    assert window.toast.secondary_button.text() == "Not now"
    assert str(window.session.account["id"]) not in window._new_look_notice_seen
    assert window.session.preferences == preferences
    assert window._look == look
    assert window.planner.geometry() == planner_geometry
    window._on_week()
    assert window.toast.isVisible() and window.toast.text() == NOTICE


def test_a_fresh_account_does_not_see_the_notice_after_setup(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    assert fresh_window.session.preferences["setup"].get("finished_at")
    assert fresh_window.session.new_account
    fresh_window._on_week()
    assert fresh_window.toast.text() != NOTICE
    account_id = str(fresh_window.session.account["id"])
    assert account_id not in fresh_window._new_look_notice_seen
    assert account_id in fresh_window._new_look_notice_exempt
    fresh_window.session.new_account = False
    fresh_window._load_look()
    fresh_window._on_week()
    assert fresh_window.toast.text() != NOTICE


def test_not_now_dismisses_the_notice_for_that_account_on_this_device(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = window.session.account["id"]
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)
    layout = deepcopy(window._layout)
    window.toast.secondary_button.click()

    assert not window.toast.isVisible()
    assert str(account_id) in window._new_look_notice_seen
    assert window.session.preferences == preferences
    assert window._look == look
    assert window._layout == layout
    stored = json.loads(device_look_file().read_text())
    assert str(account_id) in stored["new_look_notice_seen"]
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_choose_a_look_dismisses_the_notice_and_opens_settings_at_look(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = window.session.account["id"]
    preferences = deepcopy(window.session.preferences)
    look = deepcopy(window._look)
    layout = deepcopy(window._layout)
    window.toast.button.click()

    assert str(account_id) in window._new_look_notice_seen
    assert window._stack.currentWidget() is window._settings
    assert window._settings.nav.currentRow() == 0
    assert window._settings.nav.currentItem().text() == "Look"
    assert window.session.preferences == preferences
    assert window._look == look
    assert window._layout == layout
    stored = json.loads(device_look_file().read_text())
    assert str(account_id) in stored["new_look_notice_seen"]
    window._close_settings(save=False)
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_closing_the_notice_keeps_it_dismissed_on_this_device(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    window._on_week()
    account_id = str(window.session.account["id"])
    window.toast.close_button.click()

    assert not window.toast.isVisible()
    assert account_id in window._new_look_notice_seen
    stored = json.loads(device_look_file().read_text())
    assert account_id in stored["new_look_notice_seen"]
    window._load_look()
    window._on_week()
    assert not window.toast.isVisible()


def test_an_account_with_any_saved_design_look_does_not_get_the_notice(
    qapp: QApplication, fresh_window: NativeWindow
) -> None:
    window = fresh_window
    make_legacy_account(window)
    saved = json.loads(device_look_file().read_text())
    saved["layout"]["options"] = {"classic": {"look": "your"}}
    device_look_file().write_text(json.dumps(saved) + "\n")
    window._load_look()
    window._on_week()

    assert window.toast.text() != NOTICE
    assert str(window.session.account["id"]) not in window._new_look_notice_seen
