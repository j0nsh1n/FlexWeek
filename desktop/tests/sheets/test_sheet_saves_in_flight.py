# ruff: noqa: F811
"""Saving from a Material sheet while an earlier save is still on its way: a second homework save keeps the
draft and waits, a failed first save leaves the second draft and the pending first, and a fixed time's
save and delete wait.

The save is held at the client so the test decides when the answer comes. Expected titles and words
come from what the student typed and from the wait notices the sheets show.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.client import ApiError  # noqa: E402
from desktop.native.material.bridge_sheets import WAIT_DELETE, WAIT_SAVE  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheets import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.waiting import wait_until  # noqa: E402


def _hold_changes(
    session, monkeypatch: pytest.MonkeyPatch, trace: list[str] | None = None
) -> tuple[list, object]:
    original = session.client.request
    held: list = []

    def delay(method, path, body, ok, fail):
        if method == "POST" and path == "/api/changes":
            if trace is not None:
                trace.append("post")

            def tracked_ok(data):
                if trace is not None:
                    trace.append("ok")
                ok(data)

            def tracked_fail(error):
                if trace is not None:
                    trace.append("fail")
                fail(error)

            held.append((method, path, body, tracked_ok, tracked_fail))
        else:
            original(method, path, body, ok, fail)

    monkeypatch.setattr(session.client, "request", delay)
    return held, original


def _deliver_held_change(qapp: QApplication, shell: NativeWindow, held: list, original) -> None:
    """Send one held POST through the real client, then wait for that retry to finish."""
    assert held, "the held POST never left"
    original(*held.pop(0))
    wait_until(qapp, lambda: not shell.session.busy and not shell.session.dirty)


def test_a_second_homework_save_keeps_the_draft_while_the_first_is_pending(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    held, original = _hold_changes(session, monkeypatch)
    try:
        sheets.editHomework("essay")
        sheets.setText("title", "First saved title")
        sheets.save()
        assert session.busy and len(held) == 1
        assert held[0][2]["assignments"][0]["assignment"]["title"] == "First saved title"
        sheets.editHomework("essay")
        sheets.setText("title", "Second saved title")
        sheets.save()
        assert sheets.kind == "homework"
        assert sheets.form["title"] == "Second saved title"
        assert sheets.canSave is False
        assert sheets.notice == WAIT_SAVE
        assert session.assignments["essay"]["title"] == "First saved title"
        monkeypatch.setattr(session.client, "request", original)
        original(*held.pop())
        settle(qapp, shell)
        assert session.assignments["essay"]["title"] == "First saved title"
        assert session.pending_save is None
        assert not session.dirty
        assert sheets.kind == "homework"
        assert sheets.form["title"] == "Second saved title"
        assert sheets.canSave is True
        sheets.save()
        settle(qapp, shell)
        assert session.assignments["essay"]["title"] == "Second saved title"
        assert not session.dirty and session.pending_save is None
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        settle(qapp, shell)
        sheets.forceClose()


def test_a_failed_first_save_leaves_the_second_draft_and_pending_first(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    trace: list[str] = []
    held, original = _hold_changes(session, monkeypatch, trace)
    try:
        sheets.editHomework("essay")
        sheets.setText("title", "First saved title")
        sheets.save()
        sheets.editHomework("essay")
        sheets.setText("title", "Second saved title")
        sheets.save()
        assert sheets.form["title"] == "Second saved title"
        assert trace == ["post"]
        _method, _path, first_body, _ok, fail = held.pop(0)
        fail(ApiError(503, "The planner is unavailable."))
        # Window autosave (500 ms) can post the same pending payload while this waits. That is
        # the retry; unpatching and waiting 8s on retry_save() left it held and busy.
        wait_until(qapp, lambda: trace[:2] == ["post", "fail"], what=lambda: f"trace was {trace}")
        assert session.assignments["essay"]["title"] == "First saved title"
        assert session.pending_save is not None
        assert session.can_undo() is False
        assert sheets.kind == "homework"
        assert sheets.form["title"] == "Second saved title"
        assert sheets.canSave is False
        session.retry_save()
        wait_until(qapp, lambda: len(held) >= 1)
        assert session.pending_save is not None
        assert sheets.form["title"] == "Second saved title"
        assert held[0][2]["operation_id"] == first_body["operation_id"]
        _deliver_held_change(qapp, shell, held, original)
        assert trace == ["post", "fail", "post", "ok"]
        assert session.assignments["essay"]["title"] == "First saved title"
        assert session.pending_save is None
        sheets.save()
        assert held[0][2]["operation_id"] != first_body["operation_id"]
        _deliver_held_change(qapp, shell, held, original)
        assert session.assignments["essay"]["title"] == "Second saved title"
        assert trace == ["post", "fail", "post", "ok", "post", "ok"]
        session.reload()
        settle(qapp, shell)
        assert session.assignments["essay"]["title"] == "Second saved title"
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        settle(qapp, shell)
        sheets.forceClose()


def test_a_block_save_and_delete_wait_while_a_save_is_pending(
    qapp: QApplication, shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = shell.session
    held, original = _hold_changes(session, monkeypatch)
    try:
        sheets.editHomework("essay")
        sheets.setText("title", "Pending essay")
        sheets.save()
        assert session.busy
        sheets.editBlock("school", 0)
        sheets.setText("title", "Homeroom")
        sheets.save()
        assert sheets.kind == "block"
        assert sheets.form["title"] == "Homeroom"
        assert sheets.notice == WAIT_SAVE
        school = next(item for item in session.blocks if item["id"] == "school")
        assert school["title"] == "School"
        sheets.remove()
        sheets.answer("week")
        assert sheets.kind == "block"
        assert sheets.notice == WAIT_DELETE
        assert any(item["id"] == "school" for item in session.blocks)
    finally:
        monkeypatch.setattr(session.client, "request", original)
        while held:
            original(*held.pop(0))
        settle(qapp, shell)
        sheets.forceClose()

