"""A save that failed is retried with the same changes, and the server stores them once."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop.native.client import ApiError
from desktop.server import LocalServer
from desktop.tests.logic_support import fixed, qapp, server, settled, signed_in  # noqa: F401
from desktop.tests.waiting import wait_until

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


def test_retry_save_after_a_held_failure_posts_the_same_payload_once(
    qapp: QApplication, server: LocalServer, tmp_path: Path
) -> None:
    """A 503 keeps the first payload. retry_save posts that same body; the next account is empty."""
    session = signed_in(qapp, server.origin, "retry_held", create=True)
    other = signed_in(qapp, server.origin, "retry_neighbor", create=True)
    trace: list[str] = []
    held: list = []
    original = session.client.request
    initial_revision = session.revision
    neighbor_revision = other.revision

    def delay(method, path, body, ok, fail):
        if method == "POST" and path == "/api/changes":
            trace.append("post")

            def tracked_ok(data):
                trace.append("ok")
                ok(data)

            def tracked_fail(error):
                trace.append("fail")
                fail(error)

            held.append((method, path, body, tracked_ok, tracked_fail))
        else:
            original(method, path, body, ok, fail)

    session.client.request = delay  # type: ignore[method-assign]
    try:
        session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
        session.save()
        assert session.busy and len(held) == 1
        first_body = held[0][2]
        _method, _path, _body, _ok, fail = held.pop(0)
        fail(ApiError(503, "The planner is unavailable."))
        qapp.processEvents()
        assert trace == ["post", "fail"]
        assert session.pending_save is not None
        assert session.busy is False
        session.retry_save()
        wait_until(qapp, lambda: len(held) >= 1)
        assert held[0][2] == first_body
        original(*held.pop(0))
        wait_until(qapp, lambda: not session.busy and session.pending_save is None and not session.dirty)
        assert trace == ["post", "fail", "post", "ok"]
        session.reload()
        settled(qapp, session)
        other.reload()
        settled(qapp, other)
        expected = fixed("soccer", "Soccer", 0, "16:00")
        assert len(session.blocks) == 1
        assert {key: session.blocks[0][key] for key in expected} == expected
        assert session.revision == initial_revision + 1
        assert other.blocks == []
        assert other.revision == neighbor_revision
        assert other.pending_save is None
        with sqlite3.connect(f"file:{tmp_path / 'flexweek.db'}?mode=ro", uri=True) as db:
            rows = db.execute(
                "SELECT users.username, weeks.blocks, weeks.revision FROM weeks "
                "JOIN users ON users.id = weeks.user_id WHERE weeks.week_start = ? "
                "AND users.username IN (?, ?) ORDER BY users.username",
                (session.week_start, "retry_held", "retry_neighbor"),
            ).fetchall()
            operations = db.execute(
                "SELECT users.username, operations.operation_id FROM operations "
                "JOIN users ON users.id = operations.user_id WHERE operations.operation_id = ?",
                (first_body["operation_id"],),
            ).fetchall()
        saved = next(row for row in rows if row[0] == "retry_held")
        assert json.loads(saved[1]) == first_body["weeks"][0]["blocks"] == session.blocks
        assert saved[2] == initial_revision + 1
        neighbor = [row for row in rows if row[0] == "retry_neighbor"]
        assert not neighbor or (json.loads(neighbor[0][1]) == [] and neighbor[0][2] == neighbor_revision)
        assert operations == [("retry_held", first_body["operation_id"])]
    finally:
        session.client.request = original  # type: ignore[method-assign]
        while held:
            original(*held.pop(0))
        settled(qapp, session)
