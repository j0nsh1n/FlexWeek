"""The desktop app draws with Qt, never a web engine, and answers its own requests: no network port."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import contextlib
import socket
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.devices import SyncHost
from desktop.native.listening import listening_sockets
from desktop.native.window import NativeWindow
from desktop.tests.logic_support import PASSWORD, fixed, past_recovery, past_setup, sign_up
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import database, free, qapp  # noqa: F401


def web_engine_modules() -> list[str]:
    return [name for name in sys.modules if "WebEngine" in name or "QtWebEngine" in name]


def test_the_app_does_not_load_a_web_engine(qapp: QApplication) -> None:
    assert web_engine_modules() == []
    import desktop.main as desktop_main

    assert "WebEngine" not in desktop_main.__doc__
    assert web_engine_modules() == []


def test_the_probe_sees_a_listening_socket(qapp: QApplication) -> None:
    """The check below can tell: a socket this process opens to listen is found, and gone once closed."""
    if listening_sockets() is None:
        pytest.skip("reads Linux's socket tables")
    with socket.socket() as opened:
        opened.bind(("127.0.0.1", 0))
        opened.listen()
        assert any(found.startswith("tcp ") for found in listening_sockets() or [])
    assert listening_sockets() == []


def test_signing_up_and_saving_with_phone_sync_set_up_opens_no_network_port(
    qapp: QApplication, database: Path
) -> None:
    """As the app starts (desktop/main.py): phone sync set up but no phone paired, so it listens on
    nothing, and the app answers its own requests."""
    if listening_sockets() is None:
        pytest.skip("reads Linux's socket tables")
    assert listening_sockets() == []
    sync = SyncHost(database)
    sync.start_if_paired()
    window = NativeWindow(database, sync=sync)
    window.show()
    try:
        sign_up(qapp, window, "no_port", PASSWORD)
        past_recovery(qapp, window)
        past_setup(qapp, window)
        session = window.session
        session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
        session.save()
        wait_until(qapp, lambda: not session.busy and not session.dirty and not session.client._waiting)
        assert listening_sockets() == []
    finally:
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        free(window)
        sync.stop()
