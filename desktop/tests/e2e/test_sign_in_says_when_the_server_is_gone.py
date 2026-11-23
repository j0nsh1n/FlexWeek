"""When FlexWeek cannot get an answer about its saved data, the sign-in card says what to do, not that
changes were lost: saved data that cannot be opened, and an answer that does not come in time. (The
file keeps its name from when the answer came from a local server.)"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native import client as client_module
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, database, qapp, signed_out, window  # noqa: F401


def sign_in_again(qapp: QApplication, window: NativeWindow) -> str:
    bridge = window._account_bridge()
    window.session._say("")
    bridge.setUsername(USERNAME)
    bridge.setPassword(PASSWORD)
    bridge.submit()
    wait_until(qapp, lambda: not window.session.busy and bool(bridge.statusLine))
    return str(bridge.statusLine)


def signed_out_again(qapp: QApplication, window: NativeWindow) -> None:
    window.session.logout()
    wait_until(qapp, lambda: window.session.account is None and not window.session.busy)


def test_sign_in_says_when_the_saved_data_cannot_be_opened(
    qapp: QApplication, window: NativeWindow, database: Path
) -> None:
    signed_out_again(qapp, window)
    # A folder where the database file was: SQLite cannot open it.
    database.unlink()
    database.mkdir()
    assert sign_in_again(qapp, window) == (
        "FlexWeek can't open its saved data right now. Wait a minute, then sign in."
    )
    assert window.session.account is None


def test_sign_in_says_when_no_answer_comes_in_time(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    signed_out_again(qapp, window)
    stuck = threading.Event()
    answered = threading.Event()

    def never_in_time(*_arguments: object) -> client_module.Answer:
        # Held past the timeout, then a sign-in that would have worked: it must change nothing.
        stuck.wait(30)
        answered.set()
        return client_module.Answer(200, b'{"id": 1, "username": "late"}', "started", "late-token")

    monkeypatch.setattr(client_module, "ask", never_in_time)
    monkeypatch.setattr(client_module, "REQUEST_TIMEOUT_MS", 200)
    try:
        assert sign_in_again(qapp, window) == (
            "FlexWeek can't reach its server. Close FlexWeek, open it again, then sign in."
        )
        assert window.session.account is None
    finally:
        stuck.set()
    assert answered.wait(5)
    for _ in range(20):
        qapp.processEvents()
    assert window.session.client.session_token() is None
    assert window.session.account is None
