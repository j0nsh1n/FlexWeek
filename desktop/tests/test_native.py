"""Native Qt widgets against a real local API. Expected values are from the API contract."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton

    from backend.slots import hhmm_to_minutes
    from desktop.native.calendar import sunday_due
    from desktop.native.client import NativeClient
    from desktop.native.controller import NativeSession, session_days
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer

PASSWORD = "a-long-test-password"
HELD: list[object] = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-native-test"])
    yield application


@pytest.fixture()
def server(qapp: QApplication, tmp_path: Path) -> Iterator[LocalServer]:
    running = LocalServer(tmp_path / "flexweek.db", serve_frontend=False)
    running.start()
    yield running
    for obj in list(HELD):
        session = getattr(obj, "session", obj)
        client = getattr(session, "client", None)
        if client is not None:
            with contextlib.suppress(RuntimeError):
                client.reset()
    qapp.processEvents()
    running.stop()


def wait_until(qapp: QApplication, predicate, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def pump(qapp: QApplication, seconds: float = 1.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)


def signed_in(qapp: QApplication, origin: str, username: str, *, create: bool) -> NativeSession:
    session = NativeSession(origin, qapp)
    HELD.append(session)
    if create:
        session.register(username, PASSWORD)
        wait_until(qapp, lambda: session.account is not None)
        session.finish_recovery()
    else:
        session.login(username, PASSWORD)
    wait_until(qapp, lambda: session.account is not None and not session.busy)
    return session


def soccer() -> dict:
    return {
        "id": "soccer",
        "title": "Soccer",
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "start": "16:00",
    }


def table_text(window: NativeWindow) -> str:
    texts = []
    for row in range(window.week_table.rowCount()):
        for column in range(window.week_table.columnCount()):
            item = window.week_table.item(row, column)
            if item is not None and item.text():
                texts.append(item.text())
    return "\n".join(texts)


def test_native_modules_do_not_import_webengine(qapp: QApplication) -> None:
    imported = [name for name in sys.modules if "WebEngine" in name or "QtWebEngine" in name]
    assert imported == []
    import desktop.main as desktop_main

    assert "WebEngine" not in desktop_main.__doc__
    imported = [name for name in sys.modules if "WebEngine" in name or "QtWebEngine" in name]
    assert imported == []


def test_the_native_client_only_accepts_a_loopback_origin(qapp: QApplication) -> None:
    HELD.append(NativeClient("http://127.0.0.1:8765", qapp))
    with pytest.raises(ValueError, match="canonical HTTP loopback origin"):
        NativeClient("https://example.com")
    with pytest.raises(ValueError, match="canonical HTTP loopback origin"):
        NativeClient("http://127.0.0.1")


def test_session_days_cover_the_due_date_inside_the_open_week() -> None:
    assert session_days("2026-09-07", "2026-09-07T21:00") == [0]
    assert session_days("2026-09-07", "2026-09-11T21:00") == [0, 1, 2, 3, 4]
    assert session_days("2026-09-07", "2026-09-20T21:00") == [0, 1, 2, 3, 4]
    assert session_days("2026-09-07", "2026-08-31T21:00") == [0]


def test_create_account_shows_eight_codes_then_an_empty_week(qapp: QApplication, server: LocalServer) -> None:
    window = NativeWindow(server.origin)
    HELD.append(window)
    window.username.setText("alice")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
    codes = window.recovery_list.text().splitlines()
    assert len(codes) == 8
    assert all(len(code) >= 8 for code in codes)
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "weekPage")
    assert window.session.blocks == []
    assert window.session.revision == 0
    assert table_text(window) == ""


def test_saved_fixed_time_survives_sign_out_and_sign_in(qapp: QApplication, server: LocalServer) -> None:
    first = NativeWindow(server.origin)
    HELD.append(first)
    first.username.setText("alice")
    first.password.setText(PASSWORD)
    first.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: first._stack.currentWidget().objectName() == "recoveryPage")
    first.recovery_ack.setChecked(True)
    first.recovery_continue.click()
    wait_until(qapp, lambda: first._stack.currentWidget().objectName() == "weekPage")
    first.session.add_block(soccer())
    first.session.save()
    wait_until(qapp, lambda: first.session.revision == 1 and not first.session.busy)
    assert "Soccer" in table_text(first)
    first.session.logout()
    wait_until(qapp, lambda: first.session.account is None)

    second = NativeWindow(server.origin)
    HELD.append(second)
    second.username.setText("alice")
    second.password.setText(PASSWORD)
    second.findChild(QPushButton, "signIn").click()
    wait_until(qapp, lambda: second._stack.currentWidget().objectName() == "weekPage")
    assert second.session.revision == 1
    assert "Soccer" in table_text(second)


def test_a_different_monday_loads_as_its_own_empty_week(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    start = session.week_start
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    nxt = (date.fromisoformat(start) + timedelta(days=7)).isoformat()
    session.load_week(nxt)
    wait_until(qapp, lambda: session.week_start == nxt and not session.busy)
    assert session.blocks == []
    assert session.revision == 0
    session.load_week(start)
    wait_until(qapp, lambda: session.week_start == start and not session.busy)
    assert [block["title"] for block in session.blocks] == ["Soccer"]


def test_two_accounts_do_not_see_each_other_s_week(qapp: QApplication, server: LocalServer) -> None:
    alice = signed_in(qapp, server.origin, "alice", create=True)
    alice.add_block(soccer())
    alice.save()
    wait_until(qapp, lambda: alice.revision == 1 and not alice.busy)
    bob = signed_in(qapp, server.origin, "bob", create=True)
    assert bob.blocks == []
    assert bob.revision == 0
    titles = {block["title"] for block in alice.blocks}
    assert titles == {"Soccer"}


def test_a_stale_reply_after_reset_does_not_apply(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    hits: list[object] = []
    session.client.request(
        "GET",
        f"/api/week?week_start={session.week_start}",
        None,
        hits.append,
        hits.append,
    )
    session.client.reset()
    pump(qapp, 1.5)
    assert hits == []


def test_a_stale_week_save_keeps_the_draft(qapp: QApplication, server: LocalServer) -> None:
    alice = signed_in(qapp, server.origin, "alice", create=True)
    other = signed_in(qapp, server.origin, "alice", create=False)
    alice.add_block(soccer())
    alice.save()
    wait_until(qapp, lambda: alice.revision == 1 and not alice.busy)
    other.add_block(
        {
            "id": "piano",
            "title": "Piano",
            "kind": "locked",
            "duration_min": 60,
            "days": [1],
            "start": "17:00",
        }
    )
    other.save()
    wait_until(qapp, lambda: other.conflict or (other.revision == 1 and not other.busy))
    assert other.conflict
    assert other.pending_save is not None
    assert [block["title"] for block in other.blocks] == ["Piano"]
    assert other.message.startswith("Not saved.")


def test_homework_solve_places_the_session_and_explains(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    due = date.fromisoformat(session.week_start) + timedelta(days=4)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": due.isoformat() + "T21:00",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    placed_titles = {block["title"] for block in session.trace["placed"]}
    assert placed_titles == {"Soccer", "Essay"}
    assert session.trace["unplaced"] == []
    assert session.trace["complete"] is True


def test_notes_links_and_checklist_survive_a_reload(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    due = date.fromisoformat(session.week_start) + timedelta(days=4)
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "due": due.isoformat() + "T08:10",
            "estimate_min": 60,
            "revision": 0,
            "notes": "Bring the printout",
            "links": [{"label": "Spec", "url": "https://example.com/spec"}],
            "checklist": [{"id": "step-1", "text": "Outline", "done": True}],
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session_id = next(block["id"] for block in session.blocks if block.get("assignment_id") == "lab")
    session.add_homework(
        {
            **session.assignments["lab"],
            "notes": "Bring the printout and a pencil",
        }
    )
    assert next(block["id"] for block in session.blocks if block.get("assignment_id") == "lab") == session_id
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.reload()
    wait_until(qapp, lambda: not session.busy and "lab" in session.assignments)
    item = session.assignments["lab"]
    assert item["due"] == due.isoformat() + "T08:10"
    assert item["notes"] == "Bring the printout and a pencil"
    assert item["links"] == [{"label": "Spec", "url": "https://example.com/spec"}]
    assert item["checklist"][0]["done"] is True
    assert next(block["id"] for block in session.blocks if block.get("assignment_id") == "lab") == session_id


def test_completing_homework_stores_a_naive_stamp(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    due = date.fromisoformat(session.week_start) + timedelta(days=2)
    session.add_homework(
        {
            "id": "quiz",
            "title": "Quiz",
            "due": due.isoformat() + "T21:00",
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.complete_homework("quiz")
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    item = session.assignments["quiz"]
    assert item["completed"] is True
    assert item["completed_at"] is not None
    assert "T" in item["completed_at"]
    assert len(item["completed_at"]) == 16


def test_a_repeating_block_refuses_a_one_day_drag(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 60,
            "days": [0, 1, 2],
            "start": "10:00",
        }
    )
    assert session.apply_times("school", 630, 705) is False
    assert session.blocks[0]["start"] == "10:00"
    assert session.blocks[0]["duration_min"] == 60
    assert session.blocks[0]["days"] == [0, 1, 2]
    assert "ambiguous" in session.message


def test_move_and_resize_update_a_one_day_block(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    assert session.apply_times("soccer", 630, 705) is True
    assert session.blocks[0]["start"] == "10:30"
    assert session.blocks[0]["duration_min"] == 75
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)


def test_editing_one_occurrence_leaves_the_rest_of_the_series(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
            "start": "08:00",
            "category": "class",
        }
    )
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "duration_min": 390,
            "days": [2],
            "start": "09:00",
            "category": "class",
        },
        scope="occurrence",
        day=2,
    )
    days = {tuple(block["days"]): block["start"] for block in session.blocks}
    assert days[(0, 1, 3, 4)] == "08:00"
    assert days[(2,)] == "09:00"


def test_a_homework_drag_keeps_the_exact_due_time_and_that_day(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.arm_category("assignments")
    due = sunday_due(session.week_start)
    session.add_homework(
        {
            "id": "chem",
            "title": "Chemistry lab report",
            "due": due,
            "estimate_min": 90,
            "category": "assignments",
            "revision": 0,
        },
        days=[2],
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = session.blocks[0]
    assert block["kind"] == "flexible"
    assert block["days"] == [2]
    assert block.get("start") in {None, ""}
    assert block["duration_min"] == 90
    assert session.assignments["chem"]["due"] == due


def test_day_view_loads_the_saved_day_summary(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.open_day(session.week_start)
    wait_until(qapp, lambda: session.day_data is not None and not session.busy)
    assert session.planner_view == "day"
    assert session.day_data["date"] == session.week_start
    assert session.day_data["week_start"] == session.week_start
    assert session.day_data["next_action"]["kind"] == "add"
    locked_titles = {item["title"] for item in session.day_data["locked"]}
    assert "Soccer" in locked_titles


def test_month_view_is_a_five_week_saved_snapshot(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.set_view("month")
    wait_until(qapp, lambda: session.month_data is not None)
    body = session.month_data
    # Whole weeks: the Monday on or before the 1st through the Sunday on or after the last day. That
    # is 28, 35 or 42 days, so a fixed 35 passed in September and would have failed in November.
    first = date.fromisoformat(session.selected_month + "-01")
    last = (first + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    grid_start = first - timedelta(days=first.weekday())
    grid_end = last + timedelta(days=6 - last.weekday())
    assert body["days"][0]["date"] == grid_start.isoformat()
    assert body["days"][-1]["date"] == grid_end.isoformat()
    assert len(body["days"]) == (grid_end - grid_start).days + 1
    assert body["month"] == session.selected_month
    assert any(day["locked_count"] >= 1 for day in body["days"])


def test_keyboard_switches_week_day_and_month(qapp: QApplication, server: LocalServer) -> None:
    window = NativeWindow(server.origin)
    HELD.append(window)
    window.username.setText("alice")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "weekPage")
    window.setFocus()
    from PySide6.QtTest import QTest

    QTest.keyClick(window, Qt.Key.Key_D)
    wait_until(qapp, lambda: window.session.planner_view == "day")
    QTest.keyClick(window, Qt.Key.Key_M)
    wait_until(qapp, lambda: window.session.planner_view == "month")
    QTest.keyClick(window, Qt.Key.Key_W)
    wait_until(qapp, lambda: window.session.planner_view == "week")


def test_a_type_chip_opens_add_with_that_category(qapp: QApplication, server: LocalServer) -> None:
    window = NativeWindow(server.origin)
    HELD.append(window)
    window.username.setText("alice")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "weekPage")

    def fill_and_save() -> None:
        dialog = window.findChild(QDialog, "blockDialog")
        if dialog is None:
            return
        title = dialog.findChild(QLineEdit, "blockTitle")
        title.setText("Soccer practice")
        dialog.accept()

    QTimer.singleShot(0, fill_and_save)
    window.findChild(QPushButton, "chip-exercise").click()
    wait_until(qapp, lambda: any(block["title"] == "Soccer practice" for block in window.session.blocks))
    block = next(item for item in window.session.blocks if item["title"] == "Soccer practice")
    assert block["kind"] == "locked"
    assert block["category"] == "exercise"
    wait_until(qapp, lambda: not window.session.busy)


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
    assert [block["title"] for block in session.blocks] == ["Soccer"]
    assert session.can_undo()
    assert not session.can_redo()


def test_copy_paste_does_not_use_the_os_clipboard(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    clip = QGuiApplication.clipboard()
    clip.setText("sentinel-os")
    assert session.copy_selected()
    assert clip.text() == "sentinel-os"
    assert session.clipboard is not None
    assert session.clipboard["label"] == "Soccer"
    rows = session.paste_proposals(1, None)
    assert rows is not None
    assert rows[0]["day"] == 1
    assert rows[0]["block"]["start"] == "16:00"
    assert session.confirm_preview(rows, label="the copied block")
    wait_until(qapp, lambda: not session.busy and len(session.blocks) == 2)
    titles = sorted(block["title"] for block in session.blocks)
    assert titles == ["Soccer", "Soccer"]
    days = {tuple(block["days"]) for block in session.blocks}
    assert days == {(0,), (1,)}
    assert clip.text() == "sentinel-os"


def test_paste_onto_the_same_slot_stays_unchecked_until_the_time_changes(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    session.copy_selected()
    rows = session.paste_proposals(0, "16:00")
    assert rows is not None
    from desktop.native.reuse import row_conflict

    assert row_conflict(rows[0], rows, session.blocks) == "Soccer"
    assert session.confirm_preview(rows, label="the copied block") is False
    assert "Resolve conflicts" in session.message
    rows[0]["block"]["start"] = "18:00"
    rows[0]["checked"] = True
    assert session.confirm_preview(rows, label="the copied block")
    wait_until(qapp, lambda: not session.busy and len(session.blocks) == 2)


def test_a_hundredth_block_refuses_a_paste(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.select_block("soccer", 0)
    session.copy_selected()
    session.blocks = list(session.blocks) + [
        {
            "id": f"pad-{index}",
            "title": f"Pad {index}",
            "kind": "locked",
            "duration_min": 15,
            "days": [6],
            "start": "06:00",
        }
        for index in range(99)
    ]
    rows = session.paste_proposals(1, None)
    assert rows is not None
    assert session.confirm_preview(rows, label="the copied block") is False
    assert "100 blocks" in session.message


def test_homework_paste_keeps_the_assignment_and_caps_remaining_time(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    due = sunday_due(session.week_start)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": due,
            "estimate_min": 90,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and "essay" in session.assignments)
    homework = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    homework["duration_min"] = 30
    session._touch("editing Essay")
    session.save()
    wait_until(qapp, lambda: not session.busy and session.remaining_for("essay") >= 30)
    homework = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.select_block(homework["id"], homework["days"][0])
    session.copy_selected()
    first = list(session.clipboard["items"])
    session.copy_selected()
    session.clipboard["items"] = first + list(session.clipboard["items"])
    rows = session.paste_proposals(3, None)
    assert rows is not None
    usable = [row for row in rows if row["checked"]]
    assert [row["block"]["duration_min"] for row in usable] == [30, 30]
    assert all(row["block"]["assignment_id"] == "essay" for row in usable)
    assert session.confirm_preview(rows, label="the copied block")
    wait_until(qapp, lambda: not session.busy)
    ids = {block.get("assignment_id") for block in session.blocks if block.get("assignment_id")}
    assert ids == {"essay"}


def test_apply_routine_writes_a_restore_snapshot(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.save_routine("Sports week")
    wait_until(qapp, lambda: not session.busy and session.routines)
    nxt = (date.fromisoformat(session.week_start) + timedelta(days=7)).isoformat()
    routine_id = next(iter(session.routines))
    assert session.apply_routine(routine_id, nxt, [0, 1, 2, 3, 4, 5, 6])
    wait_until(qapp, lambda: session.week_start == nxt and not session.busy)
    assert any(block["title"] == "Soccer" for block in session.blocks)
    points: list[dict] = []

    def ok(data: dict) -> None:
        points.extend(data.get("restore_points") or [])

    session.client.request("GET", "/api/restore-points", None, ok, lambda _error: None)
    wait_until(qapp, lambda: bool(points))
    assert any("Sports week" in (point.get("label") or "") for point in points)


def test_unfinished_homework_keeps_the_same_assignment(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    current = session.week_start
    previous = (date.fromisoformat(current) - timedelta(days=7)).isoformat()
    session.load_week(previous)
    wait_until(qapp, lambda: session.week_start == previous and not session.busy)
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "due": previous + "T21:00",
            "estimate_min": 60,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and session.revision >= 1)
    session.load_week(current)
    wait_until(qapp, lambda: session.week_start == current and not session.busy)
    wait_until(qapp, lambda: previous in session.saved_weeks)
    items = session.unfinished()
    assert items[0]["id"] == "lab"
    rows = session.plan_unfinished("lab")
    assert rows is not None
    assert rows[0]["block"]["assignment_id"] == "lab"
    assert session.confirm_preview(rows, label="unfinished homework")
    wait_until(qapp, lambda: not session.busy)
    assert any(block.get("assignment_id") == "lab" for block in session.blocks)


def test_missed_recovery_stores_the_missed_day(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    session.recover_missed("soccer", 0)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = next(item for item in session.blocks if item["id"] == "soccer")
    assert block["missed_days"] == [0]


def test_running_late_saves_a_locked_occupancy_block(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    from datetime import datetime, time

    now = datetime.combine(date.today(), time(14, 7))
    session.preview_running_late(30, now=now)
    wait_until(qapp, lambda: session.late_preview is not None and not session.busy)
    assert session.late_preview["block"]["title"] == "Running late"
    assert session.late_preview["block"]["kind"] == "locked"
    assert session.late_preview["block"]["start"] == "14:00"
    assert session.late_preview["block"]["duration_min"] == 30
    assert session.accept_running_late()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert any(block["title"] == "Running late" for block in session.blocks)


def test_spread_keeps_assignment_identity_across_sessions(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    due = sunday_due(session.week_start)
    session.add_homework(
        {
            "id": "project",
            "title": "Project",
            "due": due,
            "estimate_min": 180,
            "category": "assignments",
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and "project" in session.assignments)
    session.blocks = []
    session._touch("clearing sessions")
    session.save()
    wait_until(qapp, lambda: not session.busy and session.blocks == [])
    session.preview_spread("project", 60, session.week_start)
    wait_until(qapp, lambda: session.spread_preview is not None and not session.busy)
    assert session.spread_preview["rows"]
    assert all(row["block"]["assignment_id"] == "project" for row in session.spread_preview["rows"])
    assert session.confirm_spread()
    wait_until(qapp, lambda: not session.busy)
    sessions = [block for block in session.blocks if block.get("assignment_id") == "project"]
    assert len(sessions) >= 2


def test_availability_round_trips_protected_time(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    window = {"kind": "meal", "days": [0, 1, 2, 3, 4], "start": "18:00", "duration_min": 30}
    assert session.save_availability([window], [], "21:00")
    wait_until(qapp, lambda: not session.busy)
    assert session.preferences is not None
    assert session.preferences["protected"][0]["kind"] == "meal"
    assert session.preferences["day_cutoff"] == "21:00"


def test_preview_dialog_leaves_a_collision_unchecked(qapp: QApplication, server: LocalServer) -> None:
    from PySide6.QtWidgets import QCheckBox

    from desktop.native.widgets import PreviewDialog

    window = NativeWindow(server.origin)
    HELD.append(window)
    window.username.setText("alice")
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "weekPage")
    window.session.add_block(soccer())
    window.session.save()
    wait_until(qapp, lambda: window.session.revision == 1 and not window.session.busy)
    window.session.select_block("soccer", 0)
    window.session.copy_selected()
    rows = window.session.paste_proposals(0, "16:00")
    assert rows is not None
    dialog = PreviewDialog(
        window,
        "Preview paste",
        "Nothing changes until you save this preview.",
        rows,
        window.session.blocks,
    )
    HELD.append(dialog)
    dialog.show()
    qapp.processEvents()
    box = dialog.findChild(QCheckBox, "previewInclude0")
    assert box is not None
    assert box.isChecked() is False
    dialog.close()


def test_focus_credits_homework_once_and_leaves_undo_alone(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.blocks[0]["start"] = "16:00"
    session.blocks[0]["days"] = [0]
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy)
    wait_until(qapp, lambda: "essay" in session.assignments)
    undos = len(session._undo)
    session.now_ms = lambda: 1_000_000
    assert session.start_focus(session.blocks[0]["id"], 0) is True
    session.now_ms = lambda: 1_000_000 + 30 * 60_000
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    wait_until(qapp, lambda: int(session.assignments["essay"].get("focus_minutes") or 0) == 30)
    assert session.assignments["essay"]["focus_sessions"] == 1
    assert session.focus is not None and session.focus["phase"] == "ended"
    assert len(session._undo) == undos
    session.now_ms = lambda: 2_000_000
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    assert session.assignments["essay"]["focus_minutes"] == 30


def test_sign_out_clears_the_focus_timer(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    account_id = session.account["id"]
    session.start_quick_focus()
    assert account_id in session.focus_store
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    assert account_id not in session.focus_store
    assert session.focus is None


def test_preference_round_trip_keeps_theme_pack_and_reminders(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(
        {
            "theme_pack": "nocturne",
            "reminders_enabled": True,
            "reminder_lead_min": 10,
            "timer_work_min": 15,
        }
    )
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and session.preferences is not None
            and session.preferences.get("theme_pack") == "nocturne"
        ),
    )
    assert session.preferences["theme"] == "nocturne"
    assert session.preferences["reminders_enabled"] is True
    assert session.preferences["reminder_lead_min"] == 10
    assert session.preferences["timer_work_min"] == 15


def test_wrong_password_keeps_the_signed_in_session(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    account = dict(session.account)
    session.login("alice", "not-the-password-at-all")
    wait_until(qapp, lambda: not session.busy)
    assert session.account == account
    session.change_password("wrong-current-password", "a-brand-new-password-ok")
    wait_until(qapp, lambda: not session.busy)
    assert session.account == account


def test_recovery_code_replaces_the_password(qapp: QApplication, server: LocalServer) -> None:
    session = NativeSession(server.origin, qapp)
    HELD.append(session)
    codes: list[str] = []
    session.recovery_codes.connect(lambda items: codes.extend(items))
    session.register("alice", PASSWORD)
    wait_until(qapp, lambda: session.account is not None and len(codes) == 8)
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    session.recover("alice", codes[0], "recovered-password-ok")
    wait_until(qapp, lambda: session.account is not None and not session.busy)
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    session.login("alice", "recovered-password-ok")
    wait_until(qapp, lambda: session.account is not None and not session.busy)


def test_restore_point_preview_then_restore(qapp: QApplication, server: LocalServer) -> None:
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


def test_week_file_round_trip_replaces_the_open_week(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    payload = json.dumps(session.week_file())
    session.blocks = []
    session._touch("clearing")
    session.save()
    wait_until(qapp, lambda: session.blocks == [] and not session.busy)
    assert session.import_week_file(payload, replace=True) is True
    wait_until(qapp, lambda: not session.busy and any(block["id"] == "soccer" for block in session.blocks))


def test_stale_restore_preview_is_refused(qapp: QApplication, server: LocalServer) -> None:
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


def test_native_window_exposes_recovery_and_focus_controls(qapp: QApplication, server: LocalServer) -> None:
    window = NativeWindow(server.origin)
    HELD.append(window)
    assert window.findChild(QPushButton, "forgotPassword") is not None
    assert window.findChild(QPushButton, "focusQuick") is not None
    assert window.findChild(QPushButton, "settingsButton") is not None
    assert window.findChild(QPushButton, "restoreButton") is not None
    assert window.findChild(QPushButton, "accountButton") is not None
    assert window.findChild(QPushButton, "moreButton") is not None
    copy_day = window.findChild(QPushButton, "copyDay")
    assert copy_day is not None
    assert copy_day.parent().objectName() == "moreOverflow"


def test_reminders_ignore_a_week_that_is_not_today(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.week_start = "2026-09-21"
    session.blocks = [soccer()]
    session.preferences = {**(session.preferences or {}), "reminders_enabled": True, "reminder_lead_min": 5}
    session.now_ms = lambda: int(datetime(2026, 9, 14, 15, 55).timestamp() * 1000)
    notices: list[dict] = []
    session.alerts.connect(notices.extend)
    session.check_alerts()
    assert notices == []
    wait_until(qapp, lambda: session._reminder_fetching is None, timeout=4.0)
    assert notices == []


def test_todays_reminders_still_fire_while_another_week_is_on_screen(
    qapp: QApplication, server: LocalServer
) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.week_start = "2026-09-21"
    session.blocks = [{**soccer(), "id": "band", "title": "Band", "start": "18:00"}]
    session._reminder_week = "2026-09-14"
    session._reminder_blocks = [soccer()]
    session.preferences = {**(session.preferences or {}), "reminders_enabled": True, "reminder_lead_min": 5}
    session.now_ms = lambda: int(datetime(2026, 9, 14, 15, 55).timestamp() * 1000)
    notices: list[dict] = []
    session.alerts.connect(notices.extend)
    session.check_alerts()
    assert [item["title"] for item in notices] == ["Soccer starts soon"]


def test_a_second_alarm_waits_until_the_first_is_dismissed(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    moment = datetime(2026, 9, 14, 7, 0)
    session.now_ms = lambda: int(moment.timestamp() * 1000)
    session.preferences = {
        **(session.preferences or {}),
        "alarms": [
            {"id": "early", "name": "Early", "time": "07:00", "days": [0], "enabled": True},
            {"id": "also", "name": "Also", "time": "07:00", "days": [0], "enabled": True},
        ],
    }
    session.last_alarm_check = None
    session.check_alerts()
    assert session.active_alarm is not None and session.active_alarm["id"] == "early"
    assert [item["id"] for item in session.alarm_queue] == ["also"]
    session.finish_alarm(False)
    assert session.active_alarm is not None and session.active_alarm["id"] == "also"
    assert session.alarm_queue == []


def test_week_file_replace_waits_for_confirmation(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.save()
    wait_until(qapp, lambda: session.revision == 1 and not session.busy)
    payload = json.dumps(session.week_file())
    session.add_block({**soccer(), "id": "band", "title": "Band", "start": "18:00"})
    assert session.import_week_file(payload) is False
    assert any(block["id"] == "band" for block in session.blocks)
    assert session.import_week_file(payload, replace=True) is True
    wait_until(qapp, lambda: not session.busy)
    assert [block["id"] for block in session.blocks] == ["soccer"]


def test_restore_clears_undo_of_the_replaced_week(qapp: QApplication, server: LocalServer) -> None:
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


def test_restore_stops_a_timer_whose_session_vanished(qapp: QApplication, server: LocalServer) -> None:
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


def test_session_expiry_forgets_the_focus_timer(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    account_id = session.account["id"]
    session.start_quick_focus()
    assert account_id in session.focus_store
    session._on_expired()
    assert session.account is None
    assert account_id not in session.focus_store
    assert session.focus is None


def test_unsaved_changes_block_account_import(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "alice", create=True)
    session.add_block(soccer())
    session.preview_account_import({"format": 3})
    assert session.transfer_preview is None
    assert "unsaved" in session.message


def test_moving_into_a_break_says_so_with_the_break_tone(qapp: QApplication, server: LocalServer) -> None:
    """The web announces every phase change. Without this the end-of-session chime setting has
    nothing to fire on, because a quick focus session rolls straight into a break in silence."""
    session = signed_in(qapp, server.origin, "phase", create=True)
    heard: list[dict] = []
    session.alerts.connect(lambda notices: heard.extend(notices))
    session.now_ms = lambda: 1_000_000
    assert session.start_quick_focus() is True
    heard.clear()
    session.now_ms = lambda: 1_000_000 + 30 * 60_000
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    focus = [notice for notice in heard if notice.get("kind") == "focus"]
    assert focus, heard
    assert focus[0]["tone"] == "soft"
    assert session.focus is not None and session.focus["phase"] in ("break", "long_break")


def test_going_back_to_work_says_so_with_the_work_tone(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "phase2", create=True)
    session.now_ms = lambda: 1_000_000
    assert session.start_quick_focus() is True
    session.now_ms = lambda: 1_000_000 + 30 * 60_000
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    heard: list[dict] = []
    session.alerts.connect(lambda notices: heard.extend(notices))
    session.now_ms = lambda: 1_000_000 + 90 * 60_000
    session.tick_focus()
    wait_until(qapp, lambda: not session.busy)
    focus = [notice for notice in heard if notice.get("kind") == "focus"]
    assert focus, heard
    assert focus[0]["tone"] == "bright"
    assert session.focus is not None and session.focus["phase"] == "work"


def test_planning_with_auto_split_leaves_focus_chunks_on_the_grid(
    qapp: QApplication, server: LocalServer
) -> None:
    """The whole feature lived in the web client; the desktop could tick the box and nothing split.
    This goes through a real solve and a real save, because the chunks have to survive validation."""
    session = signed_in(qapp, server.origin, "splitter", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(
        {
            "auto_split_pomodoro": True,
            "timer_work_min": 30,
            "timer_break_min": 15,
            "timer_long_break_min": 30,
            "timer_long_break_every": 4,
        }
    )
    wait_until(qapp, lambda: bool((session.preferences or {}).get("auto_split_pomodoro")))
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: not session.busy and session.trace is not None)
    wait_until(qapp, lambda: any(b.get("pomodoro_role") for b in session.blocks))
    chunks = [b for b in session.blocks if b.get("pomodoro_role") == "work"]
    breaks = [b for b in session.blocks if b.get("pomodoro_role") == "break"]
    assert len(chunks) == 3, [b["title"] for b in session.blocks]
    assert len(breaks) == 2
    assert all(b["kind"] == "locked" and len(b["days"]) == 1 for b in chunks + breaks)
    # Every chunk sits on the 15-minute grid the server enforces.
    assert all(hhmm_to_minutes(b["start"]) % 15 == 0 for b in chunks + breaks)
    wait_until(qapp, lambda: not session.busy)
    assert session.conflict is False


def test_planning_without_auto_split_leaves_one_block(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "nosplit", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: not session.busy and session.trace is not None)
    assert not any(b.get("pomodoro_role") for b in session.blocks)


def test_the_solver_is_asked_to_reserve_the_breaks_as_well(qapp: QApplication, server: LocalServer) -> None:
    """Splitting after the solve without asking for the extra time first would lay the chunks and
    breaks over whatever the solver placed next, because it only reserved the homework's own length."""
    session = signed_in(qapp, server.origin, "reserve", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(
        {
            "auto_split_pomodoro": True,
            "timer_work_min": 30,
            "timer_break_min": 15,
            "timer_long_break_min": 30,
            "timer_long_break_every": 4,
        }
    )
    wait_until(qapp, lambda: bool((session.preferences or {}).get("auto_split_pomodoro")))
    session.add_homework(
        {
            "id": "essay",
            "title": "Essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    sent: list[dict] = []
    original = session.client.request

    def spy(method: str, path: str, body: object, *args: object, **kwargs: object) -> object:
        if path == "/api/solve" and isinstance(body, dict):
            sent.append(body)
        return original(method, path, body, *args, **kwargs)

    session.client.request = spy  # type: ignore[method-assign]
    session.solve()
    wait_until(qapp, lambda: not session.busy and session.trace is not None)
    session.client.request = original  # type: ignore[method-assign]
    assert sent, "the solve never went out"
    asked = {block["title"]: block["duration_min"] for block in sent[0]["blocks"]}
    # 90 minutes of work plus the two 15-minute breaks that will sit between the chunks.
    assert asked["Essay"] == 120


def test_a_chunk_of_plain_homework_keeps_its_number(qapp: QApplication, server: LocalServer) -> None:
    """A flexible block with no assignment behind it keeps the numbering the split gave it."""
    session = signed_in(qapp, server.origin, "numbered", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(
        {
            "auto_split_pomodoro": True,
            "timer_work_min": 30,
            "timer_break_min": 15,
            "timer_long_break_min": 30,
            "timer_long_break_every": 4,
        }
    )
    wait_until(qapp, lambda: bool((session.preferences or {}).get("auto_split_pomodoro")))
    session.add_block(
        {
            "id": "rev",
            "title": "Revision",
            "kind": "flexible",
            "duration_min": 90,
            "days": [0, 1, 2, 3, 4],
            "category": "study",
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    wait_until(qapp, lambda: any(b.get("pomodoro_role") for b in session.blocks))
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    assert [b["title"] for b in session.blocks if b.get("pomodoro_role") == "work"] == [
        "Revision · focus 1/3",
        "Revision · focus 2/3",
        "Revision · focus 3/3",
    ]


def test_a_chunk_of_a_tracked_assignment_takes_the_assignment_title_back(
    qapp: QApplication, server: LocalServer
) -> None:
    """Not a defect in the split, and not something to fix here: the server rewrites the title of
    every block carrying an assignment_id (rewrite_session in backend/assignments.py), so the web's
    chunks are renamed in exactly the same way. Dropping the id to keep the number would stop focus
    time being credited to the assignment, which matters more than the label."""
    session = signed_in(qapp, server.origin, "tracked", create=True)
    wait_until(qapp, lambda: session.preferences is not None)
    session.save_preferences(
        {
            "auto_split_pomodoro": True,
            "timer_work_min": 30,
            "timer_break_min": 15,
            "timer_long_break_min": 30,
            "timer_long_break_every": 4,
        }
    )
    wait_until(qapp, lambda: bool((session.preferences or {}).get("auto_split_pomodoro")))
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    wait_until(qapp, lambda: session.revision >= 1 and not session.busy and not session.dirty)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    wait_until(qapp, lambda: any(b.get("pomodoro_role") for b in session.blocks))
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    chunks = [b for b in session.blocks if b.get("pomodoro_role") == "work"]
    assert len(chunks) == 3
    assert {b["title"] for b in chunks} == {"History essay"}
    # What the split is actually for still holds: the chunks are real placed blocks on one day.
    assert all(b["kind"] == "locked" and len(b["days"]) == 1 for b in chunks)
