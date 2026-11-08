"""What the session does for pairing, removing and syncing phones through the host it is given, and
when a change from a phone is held back because the week has unsaved work. No window, no phone."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.controller import NativeSession
from desktop.native.devices import SYNC_DEADLINE_MS
from desktop.tests.planner.session_without_a_window import sign_up  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


class Phone:
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


def hear(qapp: QApplication, call: Callable[..., bool]) -> None:
    heard: list[tuple] = []
    assert call(lambda result, problem: heard.append((result, problem)))
    wait_until(qapp, lambda: len(heard) == 1)
    _result, problem = heard[0]
    assert problem is None


def test_pairing_removal_and_sync_use_the_given_host(
    qapp: QApplication, sign_up: Callable[[str], NativeSession]
) -> None:
    session = sign_up("sync_host")
    account = session.account
    assert account is not None
    user_id = int(account["id"])
    assert session.begin_pairing(lambda *_args: None) is False
    bare = QObject(session)
    session.use_sync_host(bare)
    assert session.sync_linked_phones(lambda *_args: None) is False
    phone = Phone()
    host = QObject(session)
    host.service = phone  # type: ignore[attr-defined]
    session.use_sync_host(host)
    hear(qapp, session.begin_pairing)
    hear(qapp, session.end_pairing)
    hear(qapp, lambda done: session.unlink_phone("pixel", done))
    hear(qapp, session.sync_linked_phones)
    assert phone.calls == [
        ("pair_start", user_id),
        ("pair_cancel",),
        ("unlink", user_id, "pixel", True),
        ("sync_all", SYNC_DEADLINE_MS),
    ]


def test_a_remote_change_does_not_reload_a_dirty_week(
    qapp: QApplication, sign_up: Callable[[str], NativeSession]
) -> None:
    session = sign_up("sync_dirty")
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
