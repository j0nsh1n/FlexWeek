"""Native Qt widgets against a real local API. Expected values are from the API contract."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication, QPushButton

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


def test_create_account_shows_eight_codes_then_an_empty_week(
    qapp: QApplication, server: LocalServer
) -> None:
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


def test_saved_fixed_time_survives_sign_out_and_sign_in(
    qapp: QApplication, server: LocalServer
) -> None:
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


def test_a_different_monday_loads_as_its_own_empty_week(
    qapp: QApplication, server: LocalServer
) -> None:
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


def test_homework_solve_places_the_session_and_explains(
    qapp: QApplication, server: LocalServer
) -> None:
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
