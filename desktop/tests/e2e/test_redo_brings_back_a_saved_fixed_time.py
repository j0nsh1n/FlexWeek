"""Undo takes a saved fixed time off the week through the server, and Redo puts it back."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import server, signed_in, soccer  # noqa: F401
from desktop.tests.logic_support import titles
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_undo_then_redo_restores_a_saved_fixed_time(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    assert session.can_undo()
    session.undo()
    wait_until(qapp, lambda: session.revision == 2 and not session.busy)
    assert session.blocks == []
    assert session.can_redo()
    assert not session.can_undo()
    session.redo()
    wait_until(qapp, lambda: session.revision == 3 and not session.busy)
    assert titles(session.blocks) == ["Soccer"]
    assert session.can_undo()
    assert not session.can_redo()
