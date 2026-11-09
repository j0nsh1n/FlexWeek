"""Leaving an account, by signing out or by the server ending the session, forgets its focus timer."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import server, signed_in  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_signing_out_clears_the_focus_timer(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    account_id = session.account["id"]
    session.start_quick_focus()
    assert account_id in session.focus_store
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    assert account_id not in session.focus_store
    assert session.focus is None


def test_an_ended_session_forgets_the_focus_timer_and_says_so(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    account_id = session.account["id"]
    session.start_quick_focus()
    assert account_id in session.focus_store
    session._on_expired()
    assert session.message == "Your session ended. Sign in again."
    assert session.account is None
    assert account_id not in session.focus_store
    assert session.focus is None
