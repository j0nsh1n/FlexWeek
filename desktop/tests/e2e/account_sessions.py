"""Signed-in sessions on a real local server, for the few tests that need the server's own answers:
passwords, recovery codes, restore points, week files and a second sign-in."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.logic_support import fixed
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401

# Creating an account, signing in and recovering hash the password with scrypt (deliberately slow) on
# the local server's thread, which takes several times longer under the full gate's load.
HASHING_WAIT = 30.0
HELD: list[object] = []


@pytest.fixture()
def server(qapp: QApplication, tmp_path: Path) -> Iterator[LocalServer]:  # noqa: F811
    running = LocalServer(tmp_path / "flexweek.db")
    running.start()
    yield running
    for held in list(HELD):
        session = getattr(held, "session", held)
        client = getattr(session, "client", None)
        if client is not None:
            with contextlib.suppress(RuntimeError):
                client.reset()
    HELD.clear()
    qapp.processEvents()
    running.stop()


def signed_in(qapp: QApplication, origin: str, username: str, *, create: bool) -> NativeSession:  # noqa: F811
    session = NativeSession(origin, qapp)
    HELD.append(session)
    if create:
        session.register(username, PASSWORD)
        wait_until(qapp, lambda: session.account is not None, HASHING_WAIT)
        session.finish_recovery()
    else:
        session.login(username, PASSWORD)
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
    return session


def soccer() -> dict:
    return fixed("soccer", "Soccer", 0, "16:00")


def table_text(window: NativeWindow) -> str:
    """What the week says: each block's name and the line under it."""
    hours = window.week_table.hours
    if not hours.tracks:
        hours.resize(980, 640)
        hours.relayout()
    lines = []
    for track in hours.tracks:
        for drawn, _rect in hours.drawn(track):
            lines.append(f"{drawn.title}\n{drawn.detail}")
    return "\n".join(lines)
