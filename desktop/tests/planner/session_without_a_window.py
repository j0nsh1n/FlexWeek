"""A signed-in NativeSession on the in-process backend, with no window and no server, for the tests
of what the session does when a surface calls it. Replies come on the next turn of the event loop,
as the light app's do (desktop/tests/light_app.py)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.controller import NativeSession
from desktop.tests.light_app import ORIGIN, InProcessApi, _client_for
from desktop.tests.logic_support import PASSWORD
from desktop.tests.waiting import wait_until


def settled(qapp: QApplication | None, session: NativeSession) -> None:
    """Wait for the foreground request and the replies that are still on their way."""
    wait_until(qapp, lambda: not session.busy and not getattr(session.client, "pending", 0))


@pytest.fixture()
def sign_up(qapp: QApplication, tmp_path: Path) -> Iterator[Callable[[str], NativeSession]]:
    """Makes a new account and returns its session, past the recovery codes with its week and
    preferences loaded. Every session made shares one database, so a test can sign up two accounts."""
    api = InProcessApi(tmp_path / "flexweek.db")
    made: list[NativeSession] = []

    def make(username: str) -> NativeSession:
        with _client_for(api):
            session = NativeSession(ORIGIN, qapp)
        made.append(session)
        session.register(username, PASSWORD)
        wait_until(qapp, lambda: session.account is not None)
        session.finish_recovery()
        wait_until(qapp, lambda: session.account is not None and session.preferences is not None)
        settled(qapp, session)
        return session

    yield make
    for session in made:
        with contextlib.suppress(RuntimeError):
            session.client.reset()
    qapp.processEvents()
    api.close()
