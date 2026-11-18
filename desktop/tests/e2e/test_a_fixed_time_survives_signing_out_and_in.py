"""A fixed time that was saved is on the week again after the student signs out and signs back in."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import contextlib

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import HASHING_WAIT, soccer, table_text
from desktop.tests.logic_support import past_recovery, past_setup, sign_in, sign_up
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, free, qapp, server, signed_out  # noqa: F401


def test_a_saved_fixed_time_survives_signing_out_and_in(
    qapp: QApplication, server: LocalServer, signed_out: NativeWindow
) -> None:
    first = signed_out
    sign_up(qapp, first, "alice", PASSWORD)
    past_recovery(qapp, first)
    past_setup(qapp, first)
    first.session.add_block(soccer())
    first.session.save()
    wait_until(qapp, lambda: first.session.revision == 1 and not first.session.busy)
    assert "Soccer" in table_text(first)
    first.session.logout()
    wait_until(qapp, lambda: first.session.account is None)

    second = NativeWindow(server.origin)
    try:
        sign_in(qapp, second, "alice", PASSWORD)
        wait_until(qapp, lambda: second._stack.currentWidget().objectName() == "weekPage", HASHING_WAIT)
        assert second.session.revision == 1
        assert "Soccer" in table_text(second)
    finally:
        with contextlib.suppress(RuntimeError):
            second.session.client.reset()
        second.hide()
        free(second)
