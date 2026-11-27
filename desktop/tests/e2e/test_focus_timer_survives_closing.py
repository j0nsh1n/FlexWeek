"""A focus timer kept on this computer is still there after FlexWeek is closed."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json
import stat
from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop.native.controller import NativeSession
from desktop.native.focus import remaining_ms
from desktop.native.kept import KeptSession
from desktop.tests.e2e.account_sessions import HASHING_WAIT, HELD, database  # noqa: F401
from desktop.tests.logic_support import essay, place_on_monday, settled
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, qapp  # noqa: F401

# A fixed clock inside the years a week can start, so the time left does not follow today's date.
CLOCK = 1_763_000_000_000
WORK_MS = 1_800_000
BREAK_MS = 900_000
BREAK_ENDED = "The break ended while FlexWeek was closed. Press Resume to focus again."


def _kept(folder: Path) -> KeptSession:
    return KeptSession(folder / "signed-in" / "flexweek.json")


def _open(qapp: QApplication, database: Path, kept: KeptSession, now_ms: int) -> NativeSession:
    session = NativeSession(database, qapp, kept=kept)
    HELD.append(session)
    session.now_ms = lambda: now_ms  # type: ignore[method-assign]
    return session


def _register(qapp: QApplication, session: NativeSession) -> None:
    session.register("alice", PASSWORD)
    wait_until(qapp, lambda: session.account is not None, HASHING_WAIT)
    session.finish_recovery()
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
    settled(qapp, session)


def _quit(session: NativeSession) -> None:
    session.client.reset()


def _resume(qapp: QApplication, database: Path, kept: KeptSession, now_ms: int) -> NativeSession:
    session = _open(qapp, database, kept, now_ms)
    session.resume()
    wait_until(qapp, lambda: session.account is not None and not session.busy, HASHING_WAIT)
    settled(qapp, session)
    return session


def test_a_running_timer_is_back_after_flexweek_was_closed(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    assert session.start_quick_focus()
    account_id = session.account["id"]
    assert account_id in session.focus_store
    assert session.focus["phase"] == "work"
    assert session.focus["running"] is True
    assert session.focus["endsAt"] == CLOCK + WORK_MS
    assert stat.S_IMODE(kept.focus.stat().st_mode) == 0o600
    stored = json.loads(kept.focus.read_text())
    assert stored["format"] == 1
    assert str(account_id) in stored["accounts"]
    _quit(session)

    again = _resume(qapp, database, kept, CLOCK)
    assert again.focus["phase"] == "work"
    assert again.focus["running"] is True
    assert again.focus["endsAt"] == CLOCK + WORK_MS
    assert remaining_ms(again.focus, CLOCK) == WORK_MS


def test_a_break_that_ended_while_closed_pauses_on_work(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    assert session.start_quick_focus()
    session.advance_focus(False)
    assert session.focus["phase"] == "break"
    assert session.focus["endsAt"] == CLOCK + BREAK_MS
    _quit(session)

    again = _resume(qapp, database, kept, CLOCK + BREAK_MS + 1)
    assert again.message == BREAK_ENDED
    assert again.focus["phase"] == "work"
    assert again.focus["running"] is False
    assert again.focus["remainingMs"] == WORK_MS


def test_signing_out_removes_the_timer_from_the_file(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    assert session.start_quick_focus()
    account_id = session.account["id"]
    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy, HASHING_WAIT)
    assert account_id not in session.focus_store
    stored = json.loads(kept.focus.read_text())
    assert str(account_id) not in stored["accounts"]

    again = _open(qapp, database, kept, CLOCK)
    again.login("alice", PASSWORD)
    wait_until(qapp, lambda: again.account is not None and not again.busy, HASHING_WAIT)
    settled(qapp, again)
    assert again.focus is None
    assert account_id not in again.focus_store


def test_a_corrupt_focus_file_leaves_no_timer_and_no_error(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    assert session.start_quick_focus()
    account_id = session.account["id"]
    _quit(session)
    kept.focus.write_text("not a timer")

    again = _open(qapp, database, kept, CLOCK)
    assert account_id not in again.focus_store
    again.resume()
    wait_until(qapp, lambda: again.account is not None and not again.busy, HASHING_WAIT)
    settled(qapp, again)
    assert again.focus is None


def test_work_that_ended_while_closed_is_credited_once(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    session.add_homework(essay(session))
    place_on_monday(qapp, session)
    assert session.start_focus(session.blocks[0]["id"], 0)
    assert session.focus["phase"] == "work"
    ends_at = session.focus["endsAt"]
    _quit(session)

    again = _resume(qapp, database, kept, ends_at)
    assert again.focus["phase"] == "ended"
    assert again.assignments["essay"]["focus_minutes"] == 30
    _quit(again)

    third = _resume(qapp, database, kept, ends_at + 60_000)
    assert third.focus["phase"] == "ended"
    assert third.assignments["essay"]["focus_minutes"] == 30


def test_deleting_the_account_removes_its_timer_after_the_window_forgot_it(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    assert session.start_quick_focus()
    account_id = session.account["id"]
    session.delete_account(PASSWORD)
    # Delete is still in flight. The window can forget who was signed in before the answer arrives.
    session.account = None
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and session.message == "Account deleted."
            and account_id not in session.focus_store
        ),
        HASHING_WAIT,
    )
    stored = json.loads(kept.focus.read_text())
    assert str(account_id) not in stored["accounts"]
    assert account_id not in session.focus_store


def test_a_second_account_neither_sees_nor_changes_the_first_timer(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    alice = _open(qapp, database, kept, CLOCK)
    _register(qapp, alice)
    assert alice.start_quick_focus()
    alice_id = alice.account["id"]
    alice_ends = alice.focus["endsAt"]
    _quit(alice)

    bob = _open(qapp, database, kept, CLOCK)
    bob.register("bob", PASSWORD)
    wait_until(qapp, lambda: bob.account is not None, HASHING_WAIT)
    bob.finish_recovery()
    wait_until(qapp, lambda: bob.account is not None and not bob.busy, HASHING_WAIT)
    settled(qapp, bob)
    assert bob.focus is None
    assert alice_id in bob.focus_store
    bob_id = bob.account["id"]
    assert bob.start_quick_focus()
    bob.logout()
    wait_until(qapp, lambda: bob.account is None and not bob.busy, HASHING_WAIT)
    stored = json.loads(kept.focus.read_text())
    assert stored["accounts"][str(alice_id)]["endsAt"] == alice_ends
    assert str(bob_id) not in stored["accounts"]

    again = _open(qapp, database, kept, CLOCK)
    again.login("alice", PASSWORD)
    wait_until(qapp, lambda: again.account is not None and not again.busy, HASHING_WAIT)
    settled(qapp, again)
    assert again.focus["phase"] == "work"
    assert again.focus["endsAt"] == alice_ends


def test_a_huge_focus_file_gives_no_timer_and_no_error(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    assert session.start_quick_focus()
    account_id = session.account["id"]
    _quit(session)
    kept.focus.write_bytes(b"{" + b"s" * (64 * 1024))

    again = _open(qapp, database, kept, CLOCK)
    assert again.focus is None
    assert account_id not in again.focus_store
    again.resume()
    wait_until(qapp, lambda: again.account is not None and not again.busy, HASHING_WAIT)
    settled(qapp, again)
    assert again.focus is None


def test_an_out_of_range_timer_gives_no_timer_and_no_error(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    week = session.week_start
    account_id = session.account["id"]
    assert session.start_quick_focus()
    _quit(session)
    crafted = {
        "format": 1,
        "accounts": {
            str(account_id): {
                "assignmentId": None,
                "sessionId": None,
                "weekStart": week,
                "day": None,
                "start": None,
                "phase": "work",
                "cycles": 10000,
                "endsAt": CLOCK + WORK_MS,
                "remainingMs": None,
                "workMin": 181,
            }
        },
    }
    kept.focus.write_text(json.dumps(crafted), encoding="utf-8")

    again = _open(qapp, database, kept, CLOCK)
    assert account_id not in again.focus_store
    again.resume()
    wait_until(qapp, lambda: again.account is not None and not again.busy, HASHING_WAIT)
    settled(qapp, again)
    assert again.focus is None


def test_an_unknown_format_file_is_left_untouched(
    qapp: QApplication, database: Path, tmp_path: Path
) -> None:
    kept = _kept(tmp_path)
    session = _open(qapp, database, kept, CLOCK)
    _register(qapp, session)
    _quit(session)
    raw = b'{"format":2,"accounts":{"1":{"phase":"work"}}}'
    kept.focus.write_bytes(raw)

    again = _resume(qapp, database, kept, CLOCK)
    assert again.focus is None
    assert again.start_quick_focus()
    assert again.focus["phase"] == "work"
    assert kept.focus.read_bytes() == raw
