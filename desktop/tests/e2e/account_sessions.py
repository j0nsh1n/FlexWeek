"""Signed-in sessions answered by the service on worker threads, as the app runs them, for the few tests
that need its own answers: passwords, recovery codes, restore points, week files and a second sign-in."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from backend.storage import initialize
from desktop.native.controller import NativeSession
from desktop.native.window import NativeWindow
from desktop.tests.logic_support import fixed, settled
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _named, _show_material
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401

# Creating an account, signing in and recovering hash the password with scrypt (deliberately slow) on
# a worker thread, which takes several times longer under the full gate's load.
HASHING_WAIT = 30.0
HELD: list[object] = []


@pytest.fixture()
def database(qapp: QApplication, tmp_path: Path) -> Iterator[Path]:  # noqa: F811
    path = tmp_path / "flexweek.db"
    initialize(path)
    yield path
    for held in list(HELD):
        session = getattr(held, "session", held)
        client = getattr(session, "client", None)
        if client is not None:
            with contextlib.suppress(RuntimeError):
                client.reset()
    HELD.clear()
    qapp.processEvents()


def signed_in(qapp: QApplication, database: Path, username: str, *, create: bool) -> NativeSession:  # noqa: F811
    session = NativeSession(database, qapp)
    HELD.append(session)
    if create:
        session.register(username, PASSWORD)
        wait_until(qapp, lambda: session.account is not None, HASHING_WAIT)
        session.finish_recovery()
    else:
        session.login(username, PASSWORD)
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
    # Answers come from several workers, in any order: wait for the week, preferences and the rest the
    # account loads, as a student would before pressing anything.
    settled(qapp, session)
    return session


def soccer() -> dict:
    return fixed("soccer", "Soccer", 0, "16:00")


def table_text(window: NativeWindow) -> str:
    """What the week says: each block's name, as Material draws it."""
    root = _show_material(QApplication.instance(), window)
    blocks = _named(root, "weekBlock")
    titles = [str(label.property("text")) for block in blocks for label in _named(block, "title")]
    return "\n".join(titles)
