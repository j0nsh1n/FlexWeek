"""The sign-up card against the real server: eight recovery codes then an empty week, and a short username
is named before anything is sent."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.client import USERNAME_ERROR
from desktop.native.window import NativeWindow
from desktop.tests.e2e.account_sessions import HASHING_WAIT, table_text
from desktop.tests.logic_support import past_recovery, past_setup, sign_up
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, database, qapp, signed_out  # noqa: F401


def test_creating_an_account_shows_eight_codes_then_an_empty_week(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    codes = sign_up(qapp, window, "alice", PASSWORD, HASHING_WAIT)
    assert len(codes) == 8
    assert all(len(code) >= 8 for code in codes)
    past_recovery(qapp, window)
    past_setup(qapp, window)
    assert window.session.blocks == []
    assert window.session.revision == 0
    assert table_text(window) == ""


def test_a_short_username_is_named_before_the_request(qapp: QApplication, signed_out: NativeWindow) -> None:
    window = signed_out
    wait_until(qapp, lambda: window._account_bridge() is not None)
    bridge = window._account_bridge()
    bridge.showCreate()
    bridge.setUsername("ab")
    bridge.setPassword(PASSWORD)
    bridge.submit()
    assert window.session.account is None
    assert not window.session.busy, "nothing was sent"
    assert bridge.usernameProblem == USERNAME_ERROR
