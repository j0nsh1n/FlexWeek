"""The open window shows another program's change to its database, such as the assistant's, without a
restart, and keeps the student's own unsaved edits and open sheet while it does."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from backend.storage import connect
from backend.tests.fake_clock import CLOCK
from desktop.native import fields
from desktop.native.outside import file_stamp
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.logic_support import qapp  # noqa: F401
from desktop.tests.waiting import wait_until

REPO = Path(__file__).resolve().parents[3]
# Built by `cargo test -p flexweek-mcp` or `cargo build -p flexweek-mcp`; FLEXWEEK_MCP_BINARY names another.
MCP_BINARY = Path(os.environ.get("FLEXWEEK_MCP_BINARY") or REPO / "engine/target/debug/flexweek-mcp")
# The watcher looks every two seconds; this leaves room for two looks and the reload after them.
SHOWN_WITHIN_S = 6.0


def _database(window: NativeWindow, tmp_path: Path) -> Path:
    """The light window's own copy of the account (light_app keeps the first window's in window-0)."""
    database = tmp_path / "window-0" / "flexweek.db"
    assert database.exists(), "the light window keeps its database where this test looks"
    window.watch_database(database)
    return database


def _user_id(window: NativeWindow) -> int:
    account = window.session.account
    assert account is not None
    return int(account["id"])


def _titles(window: NativeWindow) -> set[str]:
    return {item["title"] for item in window.session.assignments.values()}


def _write_homework_elsewhere(database: Path, user_id: int, assignment_id: str, title: str) -> None:
    """A save through the store's own write door on a connection the window does not hold."""
    body = {
        "id": assignment_id,
        "title": title,
        "due": f"{CLOCK.today().isoformat()}T21:00",
        "estimate_min": 30,
        "priority": 3,
        "energy": "medium",
        "completed": False,
        "focus_minutes": 0,
        "focus_sessions": 0,
    }
    with connect(database) as db:
        db.begin_immediate()
        encoded = json.dumps(body, sort_keys=True)
        status, _revision = db.save_assignment(user_id, assignment_id, encoded, 0, 1000)
    assert status == "ok", f"the second writer's save was refused: {status}"


def _count_reloads(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    said: list[str] = []
    session = window.session
    load = session.load_week

    def counted(*args: object, **kwargs: object) -> None:
        said.append(str(kwargs.get("said", "")))
        load(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(session, "load_week", counted)
    return said


def _ticks(window: NativeWindow) -> Callable[[], int]:
    count = [0]
    window._outside_timer.timeout.connect(lambda: count.__setitem__(0, count[0] + 1))
    return lambda: count[0]


def _settled_on(window: NativeWindow, database: Path) -> bool:
    watch = window._outside
    return watch is not None and watch._settled == file_stamp(database)


class _Assistant:
    """The real `flexweek-mcp` on the window's database and kept session, spoken to over stdio."""

    def __init__(self, database: Path, session_file: Path) -> None:
        now = CLOCK.now().astimezone().isoformat()
        self.process = subprocess.Popen(
            [str(MCP_BINARY), "--database", str(database), "--session-file", str(session_file), "--now", now],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._stop = threading.Timer(30, self.process.kill)
        self._stop.start()
        self._request(1, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "flexweek-desktop-test", "version": "0"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, message: dict) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def _request(self, request_id: int, method: str, params: dict) -> dict:
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        assert self.process.stdout is not None
        for line in self.process.stdout:
            answer = json.loads(line)
            if answer.get("id") == request_id:
                return answer
        raise AssertionError(f"flexweek-mcp ended without answering {method}")

    def call(self, name: str, arguments: dict) -> dict:
        answer = self._request(2, "tools/call", {"name": name, "arguments": arguments})
        result = answer.get("result", {})
        assert not result.get("isError"), f"{name} was refused: {answer}"
        return json.loads(result["content"][0]["text"])

    def close(self) -> None:
        self._stop.cancel()
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


@pytest.mark.skipif(not MCP_BINARY.exists(), reason="flexweek-mcp is not built (cargo build -p flexweek-mcp)")
def test_the_assistants_new_homework_shows_in_the_open_window_without_a_restart(
    qapp: QApplication, open_light: Callable[..., NativeWindow], tmp_path: Path  # noqa: F811
) -> None:
    window = open_light()
    database = _database(window, tmp_path)
    revision = window.session.revision
    assistant = _Assistant(database, tmp_path / "window-0" / "kept-session")
    try:
        saved = assistant.call(
            "add_homework",
            {
                "operation_id": "desktop-sees-this",
                "title": "Assistant's reading",
                "due": f"{CLOCK.today().isoformat()}T21:00",
                "estimate_min": 30,
            },
        )
    finally:
        assistant.close()
    assert saved.get("ok") is True, saved
    wait_until(
        qapp,
        lambda: "Assistant's reading" in _titles(window) and not window.session.busy,
        timeout=SHOWN_WITHIN_S,
        what=lambda: f"homework on screen: {sorted(_titles(window))}",
    )
    assert window.session.revision > revision, "the week the assistant added a session to was loaded again"
    sessions = [block for block in window.session.blocks if block.get("title") == "Assistant's reading"]
    assert len(sessions) == 1, "the assistant's session is on the open week"
    assert window.session.message == "Updated from your assistant."


def test_another_programs_saved_homework_shows_within_a_few_seconds(
    qapp: QApplication, open_light: Callable[..., NativeWindow], tmp_path: Path  # noqa: F811
) -> None:
    window = open_light()
    database = _database(window, tmp_path)
    _write_homework_elsewhere(database, _user_id(window), "elsewhere-1", "Saved elsewhere")
    wait_until(
        qapp,
        lambda: "Saved elsewhere" in _titles(window) and not window.session.busy,
        timeout=SHOWN_WITHIN_S,
        what=lambda: f"homework on screen: {sorted(_titles(window))}",
    )
    assert window.session.message == "Updated from another program."


def test_unsaved_edits_are_kept_and_the_week_is_marked_changed(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = open_light()
    database = _database(window, tmp_path)
    reloads = _count_reloads(window, monkeypatch)
    # The student's edit stays unsaved for as long as this test runs.
    window._autosave.stop()
    session = window.session
    session.add_block(
        {"id": "kept-edit", "title": "Band", "kind": "locked", "days": [3],
         "start": "16:00", "duration_min": 60}
    )
    assert session.dirty
    _write_homework_elsewhere(database, _user_id(window), "elsewhere-2", "Saved elsewhere")
    wait_until(qapp, lambda: session.conflict, timeout=SHOWN_WITHIN_S, what="the week marked as changed")
    assert reloads == [], "a week with unsaved edits is not loaded again over them"
    assert any(block["id"] == "kept-edit" for block in session.blocks), "the unsaved edit is still there"
    assert session.dirty


def test_the_windows_own_save_does_not_reload_it(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = open_light()
    database = _database(window, tmp_path)
    session = window.session
    wait_until(qapp, lambda: _settled_on(window, database), timeout=SHOWN_WITHIN_S, what="the first look")
    reloads = _count_reloads(window, monkeypatch)
    before = file_stamp(database)
    session.add_block(
        {"id": "own-save", "title": "Band", "kind": "locked", "days": [3],
         "start": "16:00", "duration_min": 60}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty, what="the window's own save")
    assert file_stamp(database) != before, "the save reached the database file"
    wait_until(
        qapp, lambda: _settled_on(window, database), timeout=SHOWN_WITHIN_S, what="a look after the save"
    )
    assert reloads == [], "the window's own save is not taken for another program's"
    assert not session.conflict
    assert not session.message.startswith("Updated from")


def test_an_open_sheet_holds_the_reload_until_it_closes(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = open_light()
    database = _database(window, tmp_path)
    reloads = _count_reloads(window, monkeypatch)
    ticks = _ticks(window)
    sheet = QDialog(window)
    sheet.setModal(True)
    sheet.show()
    wait_until(qapp, lambda: QApplication.activeModalWidget() is sheet, what="the sheet open")
    _write_homework_elsewhere(database, _user_id(window), "elsewhere-3", "Saved elsewhere")
    seen = ticks()
    wait_until(qapp, lambda: ticks() >= seen + 2, timeout=SHOWN_WITHIN_S, what="two looks under the sheet")
    assert reloads == [], "nothing is loaded under an open sheet"
    assert sheet.isVisible()
    sheet.reject()
    wait_until(
        qapp,
        lambda: "Saved elsewhere" in _titles(window) and not window.session.busy,
        timeout=SHOWN_WITHIN_S,
        what="the change shown once the sheet closed",
    )
    sheet.deleteLater()


def _start_week_on(
    app: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    day: str,
    first: str,
) -> None:
    kept = tmp_path / "week-start.json"
    monkeypatch.setattr(fields, "_week_starts_file", lambda: kept)
    fields.save_week_starts_on(day)
    wait_until(app, lambda: window.session.week_start == first and not window.session.busy)


@pytest.mark.parametrize(("day", "first"), [("sunday", "2026-11-01"), ("wednesday", "2026-11-04")])
def test_a_week_from_another_day_is_not_reloaded_after_its_own_save(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    first: str,
) -> None:
    # Weeks are stored by their Monday, so a week on screen from Sunday or Wednesday is no stored
    # week of its own. The check for another program's change must read the stored weeks it covers:
    # looking for a row under the Sunday found none, took that for a change, and loaded the week
    # again after every save, which kept the window busy.
    window = open_light()
    database = _database(window, tmp_path)
    session = window.session
    _start_week_on(qapp, window, monkeypatch, tmp_path, day, first)
    reloads = _count_reloads(window, monkeypatch)
    wait_until(qapp, lambda: _settled_on(window, database), timeout=SHOWN_WITHIN_S, what="the first look")
    assert reloads == [], "nothing changed elsewhere, so the week is not loaded again"
    assert not session.message.startswith("Updated from")
    before = file_stamp(database)
    session.add_block(
        {"id": "own-save", "title": "Band", "kind": "locked", "days": [1],
         "start": "16:00", "duration_min": 60}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty, what="the window's own save")
    assert file_stamp(database) != before, "the save reached the database file"
    wait_until(
        qapp, lambda: _settled_on(window, database), timeout=SHOWN_WITHIN_S, what="a look after the save"
    )
    assert reloads == [], "the window's own save is not taken for another program's"
    assert not session.conflict


def test_another_programs_change_to_a_stored_week_shows_in_a_week_from_sunday(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The week from Sunday 1 November reads the stored weeks of 26 October and 2 November. A block
    # another program saves in the week of 2 November (its Tuesday, 3 November) shows here.
    window = open_light()
    database = _database(window, tmp_path)
    session = window.session
    _start_week_on(qapp, window, monkeypatch, tmp_path, "sunday", "2026-11-01")
    wait_until(qapp, lambda: _settled_on(window, database), timeout=SHOWN_WITHIN_S, what="the first look")
    block = {"id": "elsewhere-week", "title": "Orchestra", "kind": "locked", "days": [1],
             "start": "17:00", "duration_min": 60}
    with connect(database) as db:
        db.begin_immediate()
        row = db.read_week(_user_id(window), "2026-11-02")
        blocks = json.loads(row[0]) if row else []
        revision = row[1] if row else 0
        db.save_week(_user_id(window), "2026-11-02", json.dumps([*blocks, block]), revision)
    wait_until(
        qapp,
        lambda: any(item["id"] == "elsewhere-week" for item in session.blocks) and not session.busy,
        timeout=SHOWN_WITHIN_S,
        what=lambda: f"blocks on screen: {sorted(item['id'] for item in session.blocks)}",
    )
