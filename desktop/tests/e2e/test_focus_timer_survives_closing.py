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
from desktop.tests.logic_support import settled
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
