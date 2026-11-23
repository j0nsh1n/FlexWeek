"""The desktop app draws with Qt, never a web engine, and answers its own requests: no network port."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.logic_support import PASSWORD, fixed, past_recovery, past_setup, sign_up
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import database, qapp, signed_out  # noqa: F401

# A TCP socket's state in /proc/net/tcp when it listens.
LISTEN = "0A"


def web_engine_modules() -> list[str]:
    return [name for name in sys.modules if "WebEngine" in name or "QtWebEngine" in name]


def test_the_app_does_not_load_a_web_engine(qapp: QApplication) -> None:
    assert web_engine_modules() == []
    import desktop.main as desktop_main

    assert "WebEngine" not in desktop_main.__doc__
    assert web_engine_modules() == []


def listening_sockets() -> list[str]:
    """This process's network sockets that listen for or accept anyone: TCP in the listening state and
    every bound UDP socket, IPv4 and IPv6, read from Linux's tables by the socket's inode."""
    mine = set()
    for fd in Path("/proc/self/fd").iterdir():
        with contextlib.suppress(OSError):
            target = os.readlink(fd)
            if target.startswith("socket:["):
                mine.add(target[len("socket:[") : -1])
    found = []
    for table in ("tcp", "tcp6", "udp", "udp6"):
        lines = Path(f"/proc/self/net/{table}").read_text().splitlines()[1:]
        for line in lines:
            fields = line.split()
            local, state, inode = fields[1], fields[3], fields[9]
            if inode in mine and (table.startswith("udp") or state == LISTEN):
                found.append(f"{table} {local}")
    return found


@pytest.mark.skipif(not Path("/proc/self/net/tcp").exists(), reason="reads Linux's socket tables")
def test_signing_up_and_saving_opens_no_network_port(qapp: QApplication, signed_out: NativeWindow) -> None:
    """The app answers its own requests in this process: with no phone paired it listens on nothing."""
    assert listening_sockets() == []
    sign_up(qapp, signed_out, "no_port", PASSWORD)
    past_recovery(qapp, signed_out)
    past_setup(qapp, signed_out)
    session = signed_out.session
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty and not session.client._waiting)
    assert listening_sockets() == []
