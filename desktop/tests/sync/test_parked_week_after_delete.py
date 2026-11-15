"""A week set aside with unsaved changes forgets homework deleted in another week everywhere it holds it:
its Undo and Redo history, a save that failed and waits for Retry, and the placements of its last plan."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.storage import connect
from desktop.native.client import ApiError
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.logic_support import qapp  # noqa: F401
from desktop.tests.sync.test_outside_changes import _database, _start_week_on, _user_id
from desktop.tests.waiting import wait_until

WEEKS = [("monday", "2026-11-02", "2026-11-09"), ("sunday", "2026-11-01", "2026-11-08")]
BAND = {
    "id": "parked-edit", "title": "Band", "kind": "locked", "days": [1], "start": "18:00", "duration_min": 60,
}


def _settle(app: QApplication, window: NativeWindow, what: str) -> None:
    wait_until(app, lambda: not window.session.busy, what=what)


def _stored_blocks(window: NativeWindow, database: Path, first: str) -> list[dict]:
    session = window.session
    blocks: list[dict] = []
    with connect(database) as db:
        for week, _revision in session.stored_weeks() if first == session.week_start else []:
            row = db.read_week(_user_id(window), week)
            blocks += json.loads(row[0]) if row else []
    return blocks


def _delete_in_next_week(app: QApplication, window: NativeWindow, first: str, next_week: str) -> None:
    session = window.session
    session.load_week(next_week)
    wait_until(app, lambda: session.week_start == next_week and not session.busy, what="the next week")
    assert session.delete_homework("essay")
    wait_until(app, lambda: not session.busy and "essay" not in session.assignments, what="the delete")
    session.load_week(first)
    wait_until(app, lambda: session.week_start == first and not session.busy, what="back")


def _start(
    app: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    day: str,
    first: str,
) -> Path:
    database = _database(window, tmp_path)
    window._autosave.stop()
    window._outside_timer.stop()
    _start_week_on(app, window, monkeypatch, tmp_path, day, first)
    session = window.session
    session.add_homework(
        {"id": "essay", "title": "Essay", "due": "2026-11-20", "estimate_min": 60, "revision": 0}
    )
    session.save()
    _settle(app, window, "the essay saved")
    assert not session.conflict, session.message
    return database


@pytest.mark.parametrize(("day", "first", "next_week"), WEEKS)
@pytest.mark.parametrize("delete_elsewhere", [False, True])
def test_undo_and_redo_in_a_parked_week_never_bring_back_deleted_homework(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    first: str,
    next_week: str,
    delete_elsewhere: bool,
) -> None:
    window = open_light()
    session = window.session
    database = _start(qapp, window, monkeypatch, tmp_path, day, first)
    session.add_homework({**session.assignments["essay"], "title": "Edited essay"})
    session.save()
    _settle(qapp, window, "the title edit saved")
    session.add_block(dict(BAND))
    session.load_week(next_week)
    wait_until(qapp, lambda: session.week_start == next_week and not session.busy, what="the next week")
    if delete_elsewhere:
        assert session.delete_homework("essay")
        _settle(qapp, window, "the delete")
    session.load_week(first)
    wait_until(qapp, lambda: session.week_start == first and not session.busy, what="back")
    session.save()
    _settle(qapp, window, "the parked edit saved")
    assert not session.conflict, session.message
    session.undo()
    _settle(qapp, window, "undo of the parked edit")
    assert "parked-edit" not in {block["id"] for block in _stored_blocks(window, database, first)}, (
        "Undo of an edit made in the parked week still works"
    )
    session.redo()
    _settle(qapp, window, "redo of the parked edit")
    assert "parked-edit" in {block["id"] for block in _stored_blocks(window, database, first)}
    session.undo()
    _settle(qapp, window, "undo again")
    session.undo()
    _settle(qapp, window, "undo of the title edit")
    with connect(database) as db:
        stored = db.assignment_body(_user_id(window), "essay")
    if delete_elsewhere:
        assert stored is None, "Undo in the parked week recreated the deleted homework"
        assert "essay" not in session.assignments
    else:
        assert stored is not None and json.loads(stored)["title"] == "Essay"


@pytest.mark.parametrize(("day", "first", "next_week"), WEEKS)
def test_the_deletion_itself_can_still_be_undone_from_the_week_it_was_made_in(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    first: str,
    next_week: str,
) -> None:
    window = open_light()
    session = window.session
    _start(qapp, window, monkeypatch, tmp_path, day, first)
    session.load_week(next_week)
    wait_until(qapp, lambda: session.week_start == next_week and not session.busy, what="the next week")
    assert session.delete_homework("essay")
    wait_until(qapp, lambda: not session.busy and "essay" not in session.assignments, what="the delete")
    session.undo()
    wait_until(qapp, lambda: not session.busy and "essay" in session.assignments, what="the undo")


@pytest.mark.parametrize(("day", "first", "next_week"), WEEKS)
@pytest.mark.parametrize("delete_elsewhere", [False, True])
def test_a_failed_save_held_by_a_parked_week_retries_after_homework_is_deleted_elsewhere(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    first: str,
    next_week: str,
    delete_elsewhere: bool,
) -> None:
    window = open_light()
    session = window.session
    database = _start(qapp, window, monkeypatch, tmp_path, day, first)
    session.add_block(dict(BAND))
    request = session.client.request

    def unavailable(method: str, path: str, payload: object, ok: Callable, err: Callable) -> object:
        if method == "POST" and path == "/api/changes":
            err(ApiError(0, "simulated connection failure before write"))
            return None
        return request(method, path, payload, ok, err)

    with monkeypatch.context() as patch:
        patch.setattr(session.client, "request", unavailable)
        session.save()
        _settle(qapp, window, "the failed save")
    assert session.pending_save is not None
    failed_operation = session.pending_save["operation_id"]
    session.load_week(next_week)
    wait_until(qapp, lambda: session.week_start == next_week and not session.busy, what="the next week")
    if delete_elsewhere:
        assert session.delete_homework("essay")
        _settle(qapp, window, "the delete")
    session.load_week(first)
    wait_until(qapp, lambda: session.week_start == first and not session.busy, what="back")
    if delete_elsewhere:
        assert session.pending_save is not None
        assert session.pending_save["operation_id"] != failed_operation, (
            "a request changed after a failure takes a new operation id"
        )
    session.save()
    _settle(qapp, window, "the retry")
    assert not session.conflict, session.message
    assert not session.dirty, session.message
    stored = _stored_blocks(window, database, first)
    assert "parked-edit" in {block["id"] for block in stored}
    if delete_elsewhere:
        assert not any(block.get("assignment_id") == "essay" for block in stored)
        with connect(database) as db:
            assert db.assignment_body(_user_id(window), "essay") is None
    else:
        assert session.pending_save is None


@pytest.mark.parametrize(("day", "first", "next_week"), WEEKS)
def test_a_parked_plan_forgets_the_placements_of_deleted_homework(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    first: str,
    next_week: str,
) -> None:
    window = open_light()
    session = window.session
    _start(qapp, window, monkeypatch, tmp_path, day, first)
    waiting = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    placed = {**waiting, "days": [2], "start": "16:00"}
    session.add_block(dict(BAND))
    session.trace = {"placed": [placed, {**BAND, "id": "kept-placement"}], "unplaced": [dict(waiting)]}
    _delete_in_next_week(qapp, window, first, next_week)
    shown = {block["id"] for block in session.scheduled_blocks()}
    assert waiting["id"] not in shown, "the deleted homework's session shows again from the parked plan"
    assert "kept-placement" in shown
    assert session.trace is not None and not session.trace.get("unplaced")


@pytest.mark.parametrize(("day", "first", "next_week"), WEEKS)
@pytest.mark.parametrize("landed", [False, True], ids=["never-sent", "reply-lost"])
def test_a_delete_elsewhere_after_a_failed_save_is_done_and_undo_works_after_retry(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    first: str,
    next_week: str,
    landed: bool,
) -> None:
    # Band's save fails (never sent, or written with its reply lost), so the parked week holds a
    # save and a history step not yet acknowledged. Deleting the essay in the next week is reported
    # done, and back on the first week Retry saves Band and its Undo takes Band away, with the essay
    # still gone.
    window = open_light()
    session = window.session
    database = _start(qapp, window, monkeypatch, tmp_path, day, first)
    session.add_block(dict(BAND))
    request = session.client.request

    def fail(method, path, payload, ok, err):  # type: ignore[no-untyped-def]
        if method == "POST" and path == "/api/changes":
            if landed:
                return request(method, path, payload, lambda _data: err(ApiError(0, "reply lost")), err)
            err(ApiError(0, "not sent"))
            return None
        return request(method, path, payload, ok, err)

    with monkeypatch.context() as patch:
        patch.setattr(session.client, "request", fail)
        session.save()
        _settle(qapp, window, "the failed save")
    session.load_week(next_week)
    wait_until(qapp, lambda: session.week_start == next_week and not session.busy, what="the next week")
    assert session.delete_homework("essay")
    _settle(qapp, window, "the delete")
    assert session.message == "Deleted Essay."
    session.load_week(first)
    wait_until(qapp, lambda: session.week_start == first and not session.busy, what="back")
    session.retry_save()
    _settle(qapp, window, "the retry")
    assert not session.conflict, session.message
    assert "parked-edit" in {block["id"] for block in _stored_blocks(window, database, first)}
    session.undo()
    _settle(qapp, window, "the undo")
    assert not session.conflict, session.message
    assert "parked-edit" not in {block["id"] for block in _stored_blocks(window, database, first)}
    with connect(database) as db:
        assert db.assignment_body(_user_id(window), "essay") is None
