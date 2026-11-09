"""A phone pairs through a signed-in window on the real local server and is listed in Settings > Devices;
Remove asks first and then revokes it; Sync now with a phone linked reports no problem. The server, the
sign-in and the sync service all work on one database, as in the app."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from flexweek_engine import SyncError, SyncService
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.devices import DOT_WORDS, NO_PHONE_WORDS, UNREACHABLE_WORDS, SyncHost
from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.logic_support import past_setup
from desktop.tests.sync.support import (
    PHONE_NAME,
    label_texts,
    listed_phones,
    loopback_service,
    pair_a_phone,
    stop_sync_timer,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, free, look_file, still

pytest_plugins = ["desktop.tests.window_support", "desktop.tests.sync.support"]


@pytest.fixture()
def desk(qapp: QApplication, server: LocalServer, tmp_path: Path) -> Iterator[NativeWindow]:
    """A window signed up on the real server, whose sync service works on the server's own database."""
    database = tmp_path / "flexweek.db"
    service = loopback_service(database)
    host = SyncHost(database)
    host.service = service
    look_file().unlink(missing_ok=True)
    window = NativeWindow(server.origin, sync=host)
    window.show()
    try:
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(qapp, window)
        still(window)
        yield window
    finally:
        stop_sync_timer(window)
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        free(window)
        service.stop()


def test_a_phone_that_pairs_is_listed_on_the_card(desk: NativeWindow, phone: SyncService) -> None:
    panel = pair_a_phone(desk, phone)
    assert listed_phones(panel) == [PHONE_NAME]
    assert panel.findChild(QLabel, "devicesProblem").text() == ""
    wait_until(None, lambda: desk.sync_dot.toolTip() == DOT_WORDS["idle"])
    assert not desk.sync_dot.isHidden()


def test_remove_asks_first_then_revokes_the_phone(desk: NativeWindow, phone: SyncService) -> None:
    panel = pair_a_phone(desk, phone)
    panel.findChild(QPushButton, "removePhone").click()
    panel.dialog.findChild(QPushButton, "keepPhone").click()
    QApplication.processEvents()
    assert listed_phones(panel) == [PHONE_NAME], "keeping the phone leaves it linked"

    panel.findChild(QPushButton, "removePhone").click()
    panel.dialog.findChild(QPushButton, "confirmRemove").click()
    wait_until(None, lambda: listed_phones(panel) == [])
    assert label_texts(panel).count(NO_PHONE_WORDS) == 1
    with pytest.raises(SyncError) as refused:
        phone.sync_once(desk._sync.device_id(), 10_000)
    assert refused.value.kind == "not_paired"


def test_sync_now_with_a_linked_phone_reports_no_problem(desk: NativeWindow, phone: SyncService) -> None:
    panel = pair_a_phone(desk, phone)
    panel.findChild(QPushButton, "syncNow").click()
    wait_until(None, lambda: desk.sync_dot.toolTip() == DOT_WORDS["synced"])
    assert panel.findChild(QLabel, "devicesProblem").text() == ""
    assert UNREACHABLE_WORDS not in label_texts(panel)
