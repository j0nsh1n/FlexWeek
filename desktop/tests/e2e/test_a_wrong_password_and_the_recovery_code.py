"""Passwords against the real server: a wrong one changes nothing, and a recovery code sets a new one."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.controller import NativeSession
from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import HASHING_WAIT, HELD, PASSWORD, server, signed_in  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_wrong_password_keeps_the_signed_in_session(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    account = dict(session.account)
    session.login("alice", "not-the-password-at-all")
    wait_until(qapp, lambda: not session.busy)
    assert session.account == account
    session.change_password("wrong-current-password", "a-brand-new-password-ok")
    wait_until(qapp, lambda: not session.busy)
    assert session.account == account


def test_a_recovery_code_replaces_the_password(qapp: QApplication, server: LocalServer) -> None:
    session = NativeSession(server.origin, qapp)
    HELD.append(session)
    codes: list[str] = []
    session.recovery_codes.connect(lambda items: codes.extend(items))
    session.register("alice", PASSWORD)
    wait_until(qapp, lambda: session.account is not None and len(codes) == 8, HASHING_WAIT)
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy, HASHING_WAIT)
    session.recover("alice", codes[0], "recovered-password-ok")
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy, HASHING_WAIT)
    session.login("alice", "recovered-password-ok")
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
