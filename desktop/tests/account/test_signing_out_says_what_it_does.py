"""Signing out tells the window what it is doing, then that it is done, in that order and once each: also when
no one is signed in, where it finishes at once without asking the saved data (controller.py `logout`, run by
the session in Rust, engine/app/src/session/account.rs)."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop.native.controller import NativeSession
from desktop.tests.light_app import InProcessApi, _client_for
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def told(session: NativeSession) -> list[tuple[str, object]]:
    seen: list[tuple[str, object]] = []
    session.busy_changed.connect(lambda busy: seen.append(("busy", busy)))
    session.status.connect(lambda words: seen.append(("said", words)))
    session.account_changed.connect(lambda account: seen.append(("account", account)))
    return seen


def test_signing_out_with_no_one_signed_in_says_signing_out_then_signed_out(
    qapp: QApplication, tmp_path: Path
) -> None:
    api = InProcessApi(tmp_path / "flexweek.db")
    with _client_for(api):
        session = NativeSession(api.database, qapp)
    seen = told(session)
    session.logout()
    assert seen == [
        ("busy", True),
        ("said", "Signing out…"),
        ("busy", False),
        ("account", None),
        ("said", "Signed out."),
    ]
    assert session.message == "Signed out."
    assert not session.busy


def test_signing_out_of_an_account_says_signing_out_then_signed_out(
    qapp: QApplication, tmp_path: Path
) -> None:
    api = InProcessApi(tmp_path / "flexweek.db")
    with _client_for(api):
        session = NativeSession(api.database, qapp)
    session.register("words_student", "a-long-test-password")
    wait_until(qapp, lambda: session.account is not None and not session.busy)
    seen = told(session)
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    assert seen == [
        ("busy", True),
        ("said", "Signing out…"),
        ("busy", False),
        ("account", None),
        ("said", "Signed out."),
    ]
