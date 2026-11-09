"""Restore points on the real server: preview, restore, a preview that went stale, and what a restore
does to undo and to a running focus timer."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.server import LocalServer
from desktop.tests.e2e.account_sessions import server, signed_in, soccer  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_restore_point_previews_then_brings_the_week_back(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.create_restore_point("Before clearing")
    wait_until(qapp, lambda: bool(session.restore_points) and not session.busy)
    point_id = session.restore_points[0]["id"]
    session.blocks = []
    session._touch("clearing the week")
    session.save()
    wait_until(qapp, lambda: session.revision == 2 and session.blocks == [] and not session.busy)
    opened: list[bool] = []
    session.preview_restore_point(point_id, lambda: opened.append(True))
    wait_until(qapp, lambda: session.restore_preview is not None and not session.busy)
    assert session.restore_preview["id"] == point_id
    assert opened == [True]
    session.apply_restore_point(point_id)
    wait_until(
        qapp,
        lambda: not session.busy and any(block["id"] == "soccer" for block in session.blocks),
    )


def test_a_restore_preview_made_before_the_week_changed_is_refused(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.create_restore_point("Keep")
    wait_until(qapp, lambda: bool(session.restore_points) and not session.busy)
    point_id = session.restore_points[0]["id"]
    session.preview_restore_point(point_id)
    wait_until(qapp, lambda: session.restore_preview is not None and not session.busy)
    stale = dict(session.restore_preview)
    session.blocks = []
    session._touch("clearing")
    session.save()
    wait_until(qapp, lambda: session.revision == 2 and not session.busy)
    session.restore_preview = stale
    session.apply_restore_point(point_id)
    wait_until(qapp, lambda: not session.busy)
    assert session.blocks == []
    text = session.message.lower()
    assert any(word in text for word in ("changed", "reload", "stale", "again"))


def test_restoring_a_week_clears_the_undo_of_the_week_it_replaced(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.create_restore_point("With soccer")
    wait_until(qapp, lambda: bool(session.restore_points) and not session.busy)
    point_id = session.restore_points[0]["id"]
    session.add_block({**soccer(), "id": "band", "title": "Band", "start": "18:00"})
    session.save()
    wait_until(qapp, lambda: session.revision == 2 and session.can_undo() and not session.busy)
    session.preview_restore_point(point_id)
    wait_until(qapp, lambda: session.restore_preview is not None and not session.busy)
    session.apply_restore_point(point_id)
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and any(block["id"] == "soccer" for block in session.blocks)
            and not any(block["id"] == "band" for block in session.blocks)
        ),
    )
    assert not session.can_undo()


def test_restoring_stops_a_focus_timer_whose_session_is_gone(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.create_restore_point("Empty")
    wait_until(qapp, lambda: bool(session.restore_points) and not session.busy)
    point_id = session.restore_points[0]["id"]
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy)
    assert session.start_focus("soccer", 0) is True
    session.preview_restore_point(point_id)
    wait_until(qapp, lambda: session.restore_preview is not None and not session.busy)
    session.apply_restore_point(point_id)
    wait_until(qapp, lambda: not session.busy and session.blocks == [])
    assert session.focus is None
