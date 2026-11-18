"""A phone pairs through a signed-in window on the real local server, is listed, and the sync dot shows. The
server, the sign-in and the sync service all work on one database, as in the app."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from flexweek_engine import SyncService
from PySide6.QtWidgets import QApplication

from desktop.native.devices import SyncHost
from desktop.native.settings_copy import DOT_WORDS
from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.logic_support import past_recovery, past_setup, sign_up
from desktop.tests.sync.support import (
    PHONE_NAME,
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
        sign_up(qapp, window, USERNAME, PASSWORD)
        past_recovery(qapp, window)
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


def test_a_phone_that_pairs_is_listed_and_the_dot_shows(desk: NativeWindow, phone: SyncService) -> None:
    pair_a_phone(desk, phone)
    assert [row["name"] for row in desk._linked_phones()] == [PHONE_NAME]
    wait_until(None, lambda: desk.sync_dot.toolTip() == DOT_WORDS["idle"])
    assert not desk.sync_dot.isHidden()
