"""A block moved by hand lands and is saved, and a move let go while a save is in flight has to
survive that save's reply, which replaces the week with what was already on its way."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.client import ApiError
from desktop.native.controller import NativeSession
from desktop.tests.logic_support import fixed
from desktop.tests.planner.session_without_a_window import settled, sign_up  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


def monday_morning(session: NativeSession, clock: FakeClock) -> None:
    clock.set(datetime.fromisoformat(session.week_start).replace(hour=9))


def soccer(session: NativeSession) -> dict:
    return next(item for item in session.blocks if item["id"] == "soccer")


def test_place_block_moves_a_block_and_saves_it(
    qapp: QApplication, sign_up: Callable[[str], NativeSession], clock: FakeClock
) -> None:
    session = sign_up("place_idle")
    monday_morning(session, clock)
    session.add_block(fixed("soccer", "Soccer", 0, "16:00"))
    session.save()
    settled(qapp, session)
    landed: list[str] = []
    session.hand_placed.connect(landed.append)
    session.place_block("soccer", 0, 1, 10 * 60, 11 * 60)
    assert landed, "the move was refused, so the later save-in-flight case would prove nothing"
    settled(qapp, session)
    assert soccer(session)["days"] == [1]
    assert soccer(session)["start"] == "10:00"


def test_a_move_during_a_save_is_not_lost(
    qapp: QApplication, sign_up: Callable[[str], NativeSession], clock: FakeClock
) -> None:
    """The in-flight save answers with the week as it was. The move made while it was away is applied
    after that answer, and then saved."""
    session = sign_up("place_busy")
    monday_morning(session, clock)
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
    assert soccer(session)["days"] == [1]
    assert soccer(session)["start"] == "10:00"
    session.reload()
    settled(qapp, session)
    assert soccer(session)["days"] == [1]
    assert soccer(session)["start"] == "10:00"
