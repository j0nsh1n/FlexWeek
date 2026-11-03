"""Session actions a surface can call with no widgets on screen.

A move let go while a save is in flight has to survive that save's reply, which replaces the week
with what was already on its way. Setup's answers leave one write at a time: preferences, then
study hours, then the week. Another week's blocks come from that week, and a failed load is said
instead of being shown as an empty week.
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from desktop.tests import logic_support

pytestmark = logic_support.NEEDS_DESKTOP
qapp = logic_support.qapp
server = logic_support.server

if importlib.util.find_spec("PySide6") is not None:
    from flexweek_engine import SyncService  # type: ignore[import-untyped]
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from desktop.native.client import ApiError
    from desktop.native.devices import SYNC_DEADLINE_MS, SyncHost
    from desktop.server import LocalServer
    from desktop.tests.logic_support import (
        PASSWORD,
        fail_once,
        fixed,
        settled,
        signed_in,
        wait_until,
        week_after,
    )


def _monday_morning(session: object) -> None:
    morning = datetime.fromisoformat(session.week_start).replace(hour=9)  # type: ignore[attr-defined]
    session.now_ms = lambda: int(morning.timestamp() * 1000)  # type: ignore[attr-defined]


def _soccer(session: object) -> dict:
    return next(item for item in session.blocks if item["id"] == "soccer")  # type: ignore[attr-defined]


def test_place_block_moves_a_block_and_saves_it(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "place_idle", create=True)
    _monday_morning(session)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    landed: list[str] = []
    session.hand_placed.connect(landed.append)
    session.place_block("soccer", 0, 1, 10 * 60, 11 * 60)
    assert landed, "the move was refused, so the later save-in-flight case would prove nothing"
    settled(qapp, session)
    soccer = _soccer(session)
    assert soccer["days"] == [1]
    assert soccer["start"] == "10:00"


def test_a_move_during_a_save_is_not_lost(qapp: QApplication, server: LocalServer) -> None:
    """The in-flight save answers with the week as it was. The move made while it was away is applied
    after that answer, and then saved."""
    session = signed_in(qapp, server.origin, "place_busy", create=True)
    _monday_morning(session)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)

    landed: list[str] = []
    session.hand_placed.connect(landed.append)
    real = session.client.request
    held: list[tuple] = []

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "POST" and path.startswith("/api/changes"):
            held.append((method, path, payload, on_success, on_error))
            return
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[method-assign, assignment]
    session.blocks[0]["title"] = "Soccer club"
    session.dirty = True
    session.save()
    assert session.busy and len(held) == 1

    session.place_block("soccer", 0, 1, 10 * 60, 11 * 60)
    assert session.blocks[0]["days"] == [0] and session.blocks[0]["start"] == "16:00"
    assert landed == []

    session.client.request = real  # type: ignore[method-assign]
    real(*held[0])
    wait_until(qapp, lambda: len(landed) == 1)
    settled(qapp, session)
    soccer = _soccer(session)
    assert soccer["days"] == [1]
    assert soccer["start"] == "10:00"
    session.reload()
    settled(qapp, session)
    kept = _soccer(session)
    assert kept["days"] == [1]
    assert kept["start"] == "10:00"


def test_setup_writes_stay_in_order(qapp: QApplication, server: LocalServer) -> None:
    """Preferences, then study hours, then the week. A second request would replace the first."""
    session = signed_in(qapp, server.origin, "setup_order", create=True)
    assert session.preferences is not None
    real = session.client.request
    order: list[str] = []
    availability: list[object] = []
    inflight = 0
    peak = 0

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        nonlocal inflight, peak
        counted = (method == "PUT" and path.startswith("/api/preferences")) or (
            method == "POST" and path.startswith("/api/changes")
        )
        if not counted:
            real(method, path, payload, on_success, on_error)
            return
        inflight += 1
        peak = max(peak, inflight)
        order.append(session.message)
        if session.message == "Saving availability…":
            availability.append((payload or {}).get("work_windows"))

        def done(data: dict, then: Callable[[dict], None] = on_success) -> None:
            nonlocal inflight
            inflight -= 1
            then(data)

        def failed(error: ApiError, then: Callable[[ApiError], None] = on_error) -> None:
            nonlocal inflight
            inflight -= 1
            then(error)

        real(method, path, payload, done, failed)

    session.client.request = request  # type: ignore[method-assign, assignment]
    window = [{"days": [0, 1, 2, 3, 4], "start": "15:00", "end": "18:00"}]
    session.keep_setup(
        {"planning_style": "auto", "clock_24h": True},
        work_windows=window,
        save_week=True,
    )
    wait_until(
        qapp,
        lambda: (
            not session.setup_prefs
            and session.setup_work_windows is None
            and not session.setup_week
            and not session.busy
            and inflight == 0
        ),
    )
    settled(qapp, session)
    assert peak == 1, order
    assert order == ["Saving preferences…", "Saving availability…", "Saving…"]
    assert availability == [window]
    assert session.preferences["planning_style"] == "auto"
    assert session.preferences["clock_24h"] is True


def _saved_soccer(qapp: QApplication, server: LocalServer, name: str):
    session = signed_in(qapp, server.origin, name, create=True)
    _monday_morning(session)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    return session


def _watch_weeks(session: object) -> list[str]:
    gets: list[str] = []
    real = session.client.request  # type: ignore[attr-defined]

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "GET" and path.startswith("/api/week?"):
            gets.append(path)
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[attr-defined, method-assign, assignment]
    return gets


def test_week_blocks_uses_this_week_without_a_request(qapp: QApplication, server: LocalServer) -> None:
    session = _saved_soccer(qapp, server, "week_here")
    gets = _watch_weeks(session)
    got: list[list[dict]] = []
    session.week_blocks(session.week_start, got.append)
    assert len(got) == 1
    assert any(block["id"] == "soccer" for block in got[0])
    assert gets == []


def test_week_blocks_loads_another_week(qapp: QApplication, server: LocalServer) -> None:
    session = _saved_soccer(qapp, server, "week_there")
    gets = _watch_weeks(session)
    dest = week_after(session.week_start)
    got: list[list[dict]] = []
    session.week_blocks(dest, got.append)
    wait_until(qapp, lambda: len(got) == 1)
    settled(qapp, session)
    assert gets == [f"/api/week?week_start={dest}"]
    assert all(block["id"] != "soccer" for block in got[0])


def test_a_failed_week_load_is_said_and_not_applied(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "week_down", create=True)
    dest = week_after(session.week_start)
    fail_once(session, "GET", "/api/week")
    got: list[list[dict]] = []
    session.week_blocks(dest, got.append)
    wait_until(
        qapp,
        lambda: session.message == "Storage is unavailable. Keep your changes and try again shortly.",
    )
    assert got == []


class _Phone:
    """The calls a sync service records. No real phone and no widget."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def pair_start(self, user_id: int) -> dict:
        self.calls.append(("pair_start", user_id))
        return {"display_code": "111111"}

    def pair_cancel(self) -> None:
        self.calls.append(("pair_cancel",))

    def unlink(self, user_id: int, device_id: str, forget: bool) -> None:
        self.calls.append(("unlink", user_id, device_id, forget))

    def sync_all(self, deadline_ms: int) -> list:
        self.calls.append(("sync_all", deadline_ms))
        return []


def _hear(qapp: QApplication, call: Callable[..., bool]) -> None:
    heard: list[tuple] = []
    assert call(lambda result, problem: heard.append((result, problem)))
    wait_until(qapp, lambda: len(heard) == 1)
    _result, problem = heard[0]
    assert problem is None


def test_pairing_removal_and_sync_use_the_given_host(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "sync_host", create=True)
    account = session.account
    assert account is not None
    user_id = int(account["id"])
    assert session.begin_pairing(lambda *_args: None) is False
    bare = QObject(session)
    session.use_sync_host(bare)
    assert session.sync_linked_phones(lambda *_args: None) is False
    phone = _Phone()
    host = QObject(session)
    host.service = phone  # type: ignore[attr-defined]
    session.use_sync_host(host)
    _hear(qapp, session.begin_pairing)
    _hear(qapp, session.end_pairing)
    _hear(qapp, lambda done: session.unlink_phone("pixel", done))
    _hear(qapp, session.sync_linked_phones)
    assert phone.calls == [
        ("pair_start", user_id),
        ("pair_cancel",),
        ("unlink", user_id, "pixel", True),
        ("sync_all", SYNC_DEADLINE_MS),
    ]


def test_a_remote_change_does_not_reload_a_dirty_week(qapp: QApplication, server: LocalServer) -> None:
    session = signed_in(qapp, server.origin, "sync_dirty", create=True)
    loads: list[tuple] = []
    heard: list[bool] = []
    session.week_changed.connect(lambda: heard.append(True))

    def load_week(week_start: str | None = None, *, discard: bool = False, said: str = "This week.") -> None:
        loads.append((week_start, discard, said))

    session.load_week = load_week  # type: ignore[method-assign, assignment]
    account = session.account
    session.account = None
    assert session.accept_remote_week("Ada's phone") is True
    assert loads == []
    session.account = account

    session.busy = True
    assert session.accept_remote_week("Ada's phone") is False
    assert session.conflict is False
    assert loads == []
    session.busy = False

    session.dirty = True
    assert session.accept_remote_week("Ada's phone") is True
    assert loads == []
    assert session.conflict is True
    session.dirty = False
    session.conflict = False

    session.dirty_assignments.add("essay")
    assert session.accept_remote_week("Ada's phone") is True
    assert session.conflict is True
    assert loads == []
    session.dirty_assignments.clear()
    session.conflict = False

    session.pending_save = {"weeks": []}
    assert session.accept_remote_week("Ada's phone") is True
    assert session.conflict is True
    assert loads == []
    session.pending_save = None
    session.conflict = False

    assert heard, "a held week did not tell the window there was a conflict"
    assert session.accept_remote_week("Ada's phone") is True
    assert loads == [(session.week_start, True, "Updated from Ada's phone.")]


def test_retry_save_after_a_held_failure_posts_the_same_payload_once(
    qapp: QApplication, server: LocalServer
) -> None:
    """A 503 keeps the first payload. retry_save posts that same body; the next account is empty."""
    session = signed_in(qapp, server.origin, "retry_held", create=True)
    other = signed_in(qapp, server.origin, "retry_neighbor", create=True)
    trace: list[str] = []
    held: list = []
    original = session.client.request

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
        assert held[0][2]["operation_id"] == first_body["operation_id"]
        original(*held.pop(0))
        wait_until(qapp, lambda: not session.busy and session.pending_save is None and not session.dirty)
        assert trace == ["post", "fail", "post", "ok"]
        assert [block["title"] for block in session.blocks] == ["Soccer"]
        assert other.blocks == []
        assert other.pending_save is None
    finally:
        session.client.request = original  # type: ignore[method-assign]
        while held:
            original(*held.pop(0))
        settled(qapp, session)


def _hold_the_save(session: object) -> None:
    """Start a save and keep its reply. The session stays busy, and the reply is never delivered."""
    real = session.client.request  # type: ignore[attr-defined]

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "POST" and path.startswith("/api/changes"):
            return
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[attr-defined, method-assign, assignment]
    session.save()  # type: ignore[attr-defined]
    assert session.busy  # type: ignore[attr-defined]
    session.client.request = real  # type: ignore[attr-defined, method-assign]


def _preference_puts(session: object) -> list[dict]:
    puts: list[dict] = []
    real = session.client.request  # type: ignore[attr-defined]

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "PUT" and path.startswith("/api/preferences"):
            puts.append(dict(payload or {}))
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[attr-defined, method-assign, assignment]
    return puts


def test_setup_answers_do_not_cross_a_sign_out(qapp: QApplication, server: LocalServer) -> None:
    """Answers kept while a save is in flight belong to that account. Signing out drops them, and so
    does signing a different account in, so the next flush cannot store them there."""
    session = signed_in(qapp, server.origin, "alice_cross", create=True)
    _hold_the_save(session)
    session.keep_setup({"planning_style": "manual", "clock_24h": True})
    assert session.setup_prefs == {"planning_style": "manual", "clock_24h": True}

    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    left_at_sign_out = dict(session.setup_prefs)

    session.register("bob_cross", PASSWORD)
    wait_until(qapp, lambda: session.account is not None and not session.busy)
    session.finish_recovery()
    wait_until(qapp, lambda: session.preferences is not None and not session.busy)
    settled(qapp, session)
    puts = _preference_puts(session)
    session.flush_setup()
    settled(qapp, session)
    assert puts == []
    assert left_at_sign_out == {}
    assert session.setup_work_windows is None
    assert session.setup_week is False
    bob = session.preferences
    assert bob is not None
    assert bob.get("planning_style", "suggest") == "suggest"
    assert bob.get("clock_24h", False) is False

    _hold_the_save(session)
    session.keep_setup({"planning_style": "manual", "clock_24h": True})
    puts = _preference_puts(session)
    session.register("carol_cross", PASSWORD)
    wait_until(
        qapp,
        lambda: (
            session.account is not None and session.account["username"] == "carol_cross" and not session.busy
        ),
    )
    assert session.setup_prefs == {}
    assert puts == []
    # The held save would keep this week on screen. Discard it and read the new account's own
    # preferences back: the queued answers must not have been stored for them.
    session.load_week(session.week_start, discard=True)
    wait_until(qapp, lambda: not session.busy)
    settled(qapp, session)
    carol = session.preferences
    assert carol is not None
    assert carol.get("planning_style", "suggest") == "suggest"
    assert carol.get("clock_24h", False) is False


def test_pairing_starts_a_fresh_host(
    qapp: QApplication,
    server: LocalServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first phone has no service running. Pairing starts that host, then asks it for a code."""
    session = signed_in(qapp, server.origin, "pair_fresh", create=True)
    account = session.account
    assert account is not None
    database = tmp_path / "flexweek.db"
    started: list[Path] = []

    def loopback_start(path: Path) -> SyncService:
        started.append(path)
        (path.parent / "sync").mkdir(parents=True, exist_ok=True)
        return SyncService.start(
            str(path),
            str(path.parent / "sync" / "device.key"),
            "Desk",
            True,
            "127.0.0.1:0",
            1000,
        )

    monkeypatch.setattr("desktop.native.devices.start_service", loopback_start)
    host = SyncHost(database)
    assert host.service is None
    session.use_sync_host(host)
    heard: list[tuple[object, Exception | None]] = []
    try:
        assert session.begin_pairing(lambda result, problem: heard.append((result, problem))) is True
        wait_until(qapp, lambda: len(heard) == 1)
        result, problem = heard[0]
        assert problem is None
        assert started == [database]
        assert isinstance(result, dict)
        assert re.fullmatch(r"\d{4} \d{4}", str(result["display_code"]))
    finally:
        host.stop()


def test_setup_answers_are_saved_when_preferences_arrive(qapp: QApplication, server: LocalServer) -> None:
    """Answers kept while preferences are still absent go out once that load finishes."""
    session = signed_in(qapp, server.origin, "prefs_late", create=True)
    assert session.preferences is not None
    session.preferences = None
    puts = _preference_puts(session)
    session.keep_setup({"planning_style": "manual", "clock_24h": True})
    assert session.setup_prefs == {"planning_style": "manual", "clock_24h": True}
    assert puts == []
    session._fetch_preferences()
    wait_until(qapp, lambda: session.preferences is not None)
    settled(qapp, session)
    assert [item["planning_style"] for item in puts] == ["manual"]
    assert [item["clock_24h"] for item in puts] == [True]
    assert session.setup_prefs == {}
