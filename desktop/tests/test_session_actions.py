"""Session actions a surface can call with no widgets on screen.

A move let go while a save is in flight has to survive that save's reply, which replaces the week
with what was already on its way. Setup's answers leave one write at a time: preferences, then
study hours, then the week.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from datetime import datetime

from desktop.tests import logic_support

pytestmark = logic_support.NEEDS_DESKTOP
qapp = logic_support.qapp
server = logic_support.server

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.client import ApiError
    from desktop.server import LocalServer
    from desktop.tests.logic_support import fixed, settled, signed_in, wait_until


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
        lambda: not session.setup_prefs
        and session.setup_work_windows is None
        and not session.setup_week
        and not session.busy
        and inflight == 0,
    )
    settled(qapp, session)
    assert peak == 1, order
    assert order == ["Saving preferences…", "Saving availability…", "Saving…"]
    assert availability == [window]
    assert session.preferences["planning_style"] == "auto"
    assert session.preferences["clock_24h"] is True
