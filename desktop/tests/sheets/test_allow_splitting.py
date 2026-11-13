"""Allow splitting on an In one go homework that does not fit spreads its whole estimate over sessions,
every minute with a time."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.client import ApiError
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.sheets.support_homework_week import settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

WEEKDAYS = {"days": [0, 1, 2, 3, 4], "start": "19:00", "end": "21:00"}
MONDAY_16_30 = datetime(2026, 11, 2, 16, 30)


def test_allow_splitting_replaces_one_unplaced_session_with_the_full_estimate(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    CLOCK.set(MONDAY_16_30)
    window = open_light()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(qapp, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
    # 180 minutes in evenings that hold two hours each, so it cannot be placed whole.
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "estimate_min": 180,
            "revision": 0,
            "due": (monday + timedelta(days=9)).isoformat() + "T23:59",
        }
    )
    session.save()
    settled(qapp, window)
    assert session.allow_splitting("lab")

    def pieces() -> list[dict]:
        return [block for block in session.blocks if block.get("assignment_id") == "lab"]

    def split_complete() -> bool:
        return (
            not session.busy
            and not session.dirty
            and len(pieces()) == 3
            and all(block.get("start") for block in pieces())
        )

    wait_until(
        qapp,
        split_complete,
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {pieces()}, needs time {session.needs_time}",
    )
    settled(qapp, window)
    assert len(pieces()) == 3, pieces()
    assert all(block.get("start") for block in pieces()), pieces()
    assert sum(block.get("duration_min") or 0 for block in pieces()) == 180, pieces()


def test_allow_splitting_places_every_session_when_the_read_lands_before_plan(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    """The same lab, with the Plan that Allow splitting starts held until the server's numbers for the three
    new sessions have been read (planned 180). The lab is due 9 days out, so a fair share would give it
    180 x 5 / 8 = 112.5, a quarter hour up 120, this week (Mon to Fri of the 8 study days to the Wednesday
    after next) and keep 60 back. The sessions Allow splitting makes get no fair share: all three, 180 in
    all, get a time this week, whichever comes first, the read or the Plan."""
    CLOCK.set(MONDAY_16_30)
    window = open_light()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(qapp, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "estimate_min": 180,
            "revision": 0,
            "due": (monday + timedelta(days=9)).isoformat() + "T23:59",
        }
    )
    session.save()
    settled(qapp, window)
    real_solve = session.solve
    planned_when_plan_ran: list[object] = []

    def solve_after_the_read(**kwargs) -> None:
        if not kwargs.get("join"):
            real_solve(**kwargs)
            return
        if session.assignments["lab"].get("planned_min") != 180:
            QTimer.singleShot(10, lambda: solve_after_the_read(**kwargs))
            return
        planned_when_plan_ran.append(session.assignments["lab"].get("planned_min"))
        real_solve(**kwargs)

    session.solve = solve_after_the_read  # type: ignore[method-assign]
    assert session.allow_splitting("lab")

    def pieces() -> list[dict]:
        return [block for block in session.blocks if block.get("assignment_id") == "lab"]

    wait_until(
        qapp,
        lambda: bool(planned_when_plan_ran)
        and not session.busy
        and not session.dirty
        and len(pieces()) == 3
        and all(block.get("start") for block in pieces()),
        timeout=20,
        what=lambda: f"{session.message!r}, plan saw {planned_when_plan_ran}, pieces {pieces()}",
    )
    settled(qapp, window)
    assert planned_when_plan_ran == [180]
    assert sum(block["duration_min"] for block in pieces()) == 180, pieces()


def test_a_later_replan_all_gives_the_split_homework_its_fair_share(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    """Only the Plan that Allow splitting starts skips the fair share. After it placed all three sessions,
    Replan all plans them again under the usual rule: 180 x 5 / 8 = 112.5, a quarter hour up 120 this week
    (two of the 60 minute sessions), and the other 60 waits with no time."""
    CLOCK.set(MONDAY_16_30)
    window = open_light()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(qapp, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "estimate_min": 180,
            "revision": 0,
            "due": (monday + timedelta(days=9)).isoformat() + "T23:59",
        }
    )
    session.save()
    settled(qapp, window)
    assert session.allow_splitting("lab")

    def pieces() -> list[dict]:
        return [block for block in session.blocks if block.get("assignment_id") == "lab"]

    wait_until(
        qapp,
        lambda: not session.busy
        and not session.dirty
        and len(pieces()) == 3
        and all(block.get("start") for block in pieces()),
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {pieces()}",
    )
    settled(qapp, window)
    session.solve(everything=True)
    wait_until(
        qapp,
        lambda: not session.planning and not session.busy and not session.dirty,
        timeout=20,
        what="Replan all finished",
    )
    settled(qapp, window)
    placed = sorted(block["duration_min"] for block in pieces() if block.get("start"))
    waiting = sorted(block["duration_min"] for block in pieces() if not block.get("start"))
    assert (placed, waiting) == ([60, 60], [60]), pieces()


def _lab_due_in_nine_days(app: QApplication, opener: Callable[..., NativeWindow]) -> NativeWindow:
    """Monday 16:30, evenings of two hours Mon to Fri, and the 180 minute "In one go" lab due 9 days out."""
    CLOCK.set(MONDAY_16_30)
    window = opener()
    session = window.session
    assert session.save_availability([], None, [WEEKDAYS])
    settled(app, window)
    session.selected_day = session.today_iso()
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "lab",
            "title": "Lab",
            "estimate_min": 180,
            "revision": 0,
            "due": (monday + timedelta(days=9)).isoformat() + "T23:59",
        }
    )
    session.save()
    settled(app, window)
    return window


def _fail_the_second_save(session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow splitting saves twice: the homework, then its sessions. The second save fails, once."""
    real = session.client.request
    saves: list[str] = []

    def request(method, path, payload, on_success, on_error):
        if method == "POST" and path.startswith("/api/changes"):
            saves.append(path)
            if len(saves) == 2:
                on_error(ApiError(500, "down"))
                return None
        return real(method, path, payload, on_success, on_error)

    monkeypatch.setattr(session.client, "request", request)


def _lab_pieces(session) -> list[dict]:
    return [block for block in session.blocks if block.get("assignment_id") == "lab"]


def _plan_by_hand(app: QApplication, window: NativeWindow) -> tuple[list[int], list[int]]:
    """Plan my homework; the lab's placed and waiting session lengths."""
    session = window.session
    session.solve()
    wait_until(
        app,
        lambda: not session.planning and not session.busy and not session.dirty,
        timeout=20,
        what="Plan finished",
    )
    settled(app, window)
    pieces = _lab_pieces(session)
    return (
        sorted(block["duration_min"] for block in pieces if block.get("start")),
        sorted(block["duration_min"] for block in pieces if not block.get("start")),
    )


def test_a_failed_allow_splitting_save_keeps_the_promise_after_retry(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The save that adds Allow splitting's three sessions fails; they stay in the app and Retry saves them.
    No plan that includes them has been saved, so the next Plan by hand still places all three this week,
    180 in all, with no fair share (which would give 180 x 5 / 8, a quarter hour up 120, and keep 60 back).
    Once that plan is saved, the promise ends."""
    window = _lab_due_in_nine_days(qapp, open_light)
    session = window.session
    _fail_the_second_save(session, monkeypatch)
    assert session.allow_splitting("lab")
    wait_until(
        qapp,
        lambda: session.message == "Not saved. down" and not session.busy,
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {_lab_pieces(session)}",
    )
    # Not `settled` yet: it saves what is pending, which is the Retry below.
    assert session._split_whole == {block["id"] for block in _lab_pieces(session)} != set()

    session.retry_save()
    wait_until(
        qapp,
        lambda: not session.busy and not session.dirty and session.pending_save is None,
        timeout=20,
        what=lambda: f"{session.message!r}",
    )
    settled(qapp, window)
    assert [bool(block.get("start")) for block in _lab_pieces(session)] == [False, False, False]
    assert _plan_by_hand(qapp, window) == ([60, 60, 60], [])
    assert session._split_whole == set()


def test_ids_left_by_discarded_allow_splitting_sessions_are_harmless(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The save of Allow splitting's sessions fails and the student discards them (the week reloaded as
    saved): their ids are still remembered but match no session. A Spread by hand afterwards (60 minute
    sessions from today) is ordinary even where it makes sessions with those same ids: it starts no Plan,
    none of its sessions is promised a place, and Plan by hand gives the fair share: 180 x 5 / 8 = 112.5, a
    quarter hour up 120 (two 60 minute sessions), and 60 waits."""
    window = _lab_due_in_nine_days(qapp, open_light)
    session = window.session
    _fail_the_second_save(session, monkeypatch)
    assert session.allow_splitting("lab")
    wait_until(
        qapp,
        lambda: session.message == "Not saved. down" and not session.busy,
        timeout=20,
        what=lambda: f"{session.message!r}",
    )
    stale = set(session._split_whole)
    assert len(stale) == 3
    session.load_week(session.week_start, discard=True)
    settled(qapp, window)
    assert _lab_pieces(session) == []
    assert session._split_whole == stale

    session.preview_spread("lab", 60, session.today_iso())
    wait_until(qapp, lambda: session.spread_preview is not None, timeout=20, what="Spread preview")
    assert session.confirm_spread()
    wait_until(
        qapp,
        lambda: not session.busy and not session.dirty and len(_lab_pieces(session)) == 3,
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {_lab_pieces(session)}",
    )
    settled(qapp, window)
    assert not session._split_whole & {block["id"] for block in _lab_pieces(session)}
    assert [bool(block.get("start")) for block in _lab_pieces(session)] == [False, False, False]
    assert _plan_by_hand(qapp, window) == ([60, 60], [60])


@pytest.mark.parametrize("preview", ["fails", "comes back empty"])
def test_an_ordinary_spread_after_allow_splitting_made_nothing_gets_the_fair_share(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    preview: str,
) -> None:
    """Allow splitting's preview fails (FlexWeek cannot be reached) or comes back with no sessions, so Allow
    splitting made nothing. The student then spreads the lab by hand (60 minute sessions from today). That is
    an ordinary Spread: no Plan starts by itself and no session is promised a place, so Plan by hand gives the
    fair share: 180 x 5 / 8 = 112.5, a quarter hour up 120 (two 60 minute sessions), and 60 waits."""
    window = _lab_due_in_nine_days(qapp, open_light)
    session = window.session
    real = session.client.request
    answered: list[str] = []

    def request(method, path, payload, on_success, on_error):
        if not answered and method == "POST" and path.endswith("/spread"):
            answered.append(path)
            if preview == "fails":
                on_error(ApiError(0, "unreachable"))
            else:
                on_success({"sessions": [], "remaining_min": 0})
            return None
        return real(method, path, payload, on_success, on_error)

    monkeypatch.setattr(session.client, "request", request)
    assert session.allow_splitting("lab")
    wait_until(
        qapp,
        lambda: bool(answered) and not session.busy and session.spread_preview is None,
        timeout=20,
        what=lambda: f"{session.message!r}",
    )
    settled(qapp, window)
    assert session._allow_split_pending is None
    assert _lab_pieces(session) == []

    session.preview_spread("lab", 60, session.today_iso())
    wait_until(qapp, lambda: session.spread_preview is not None, timeout=20, what="Spread preview")
    assert session.confirm_spread()
    wait_until(
        qapp,
        lambda: not session.busy and not session.dirty and len(_lab_pieces(session)) == 3,
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {_lab_pieces(session)}",
    )
    settled(qapp, window)
    assert [bool(block.get("start")) for block in _lab_pieces(session)] == [False, False, False]
    assert session._split_whole == set()
    assert _plan_by_hand(qapp, window) == ([60, 60], [60])


def test_allow_splitting_refused_for_a_full_week_forgets_its_sessions(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
) -> None:
    """A week of 98 blocks other than the lab: its three sessions would make 101, over the 100 a week
    holds, so they are not added and nothing is saved. The ids its Plan would have placed with no fair share
    are forgotten, with that Plan."""
    window = _lab_due_in_nine_days(qapp, open_light)
    session = window.session
    others = [block for block in session.blocks if block.get("assignment_id") != "lab"]
    for n in range(98 - len(others)):
        session.add_block(
            {
                "id": f"note-{n}",
                "title": "Note",
                "kind": "locked",
                "days": [6],
                "start": f"{(5 * n) // 60:02d}:{(5 * n) % 60:02d}",
                "duration_min": 5,
            }
        )
    session.save()
    settled(qapp, window)
    assert len([block for block in session.blocks if block.get("assignment_id") != "lab"]) == 98

    assert session.allow_splitting("lab")
    wait_until(
        qapp,
        lambda: "would exceed 100 blocks" in session.message and not session.busy,
        timeout=20,
        what=lambda: f"{session.message!r}",
    )
    settled(qapp, window)
    assert session._split_whole == set()
    assert session._plan_after_save == set()


@pytest.mark.parametrize("failure", ["planner unreachable", "plan save refused"])
def test_when_the_plan_after_allow_splitting_fails_the_next_plan_places_all_three(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """Allow splitting's three sessions are saved, but the Plan it starts fails: the planner cannot be
    reached, or the plan's save is refused (another window changed the week) and the week is reloaded as
    saved. No plan that includes them has been saved, so the next Plan by hand still places all three this
    week, 180 in all, with no fair share (which would give 180 x 5 / 8, a quarter hour up 120, and keep 60
    back)."""
    window = _lab_due_in_nine_days(qapp, open_light)
    session = window.session
    real = session.client.request
    failing = {"on": True}

    def request(method, path, payload, on_success, on_error):
        if failing["on"] and method == "POST":
            if failure == "planner unreachable" and path.startswith("/api/solve"):
                failing["on"] = False
                on_error(ApiError(0, "unreachable"))
                return None
            if failure == "plan save refused" and path.startswith("/api/changes") and any(
                block.get("start")
                for week in payload.get("weeks") or []
                for block in week.get("blocks") or []
                if block.get("assignment_id") == "lab"
            ):
                failing["on"] = False
                on_error(ApiError(409, "This week changed in another window."))
                return None
        return real(method, path, payload, on_success, on_error)

    monkeypatch.setattr(session.client, "request", request)

    def pieces() -> list[dict]:
        return [block for block in session.blocks if block.get("assignment_id") == "lab"]

    assert session.allow_splitting("lab")
    wait_until(
        qapp,
        lambda: not failing["on"] and not session.busy and not session.planning,
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {pieces()}",
    )
    if failure == "plan save refused":
        assert session.conflict
        session.load_week(session.week_start, discard=True)
    settled(qapp, window)
    assert len(pieces()) == 3
    assert not any(block.get("start") for block in pieces()), pieces()

    session.solve()
    wait_until(
        qapp,
        lambda: not session.planning
        and not session.busy
        and not session.dirty
        and all(block.get("start") for block in pieces()),
        timeout=20,
        what=lambda: f"{session.message!r}, pieces {pieces()}",
    )
    settled(qapp, window)
    assert sorted(block["duration_min"] for block in pieces()) == [60, 60, 60], pieces()
    assert session._split_whole == set()
