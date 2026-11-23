"""A window request that waits for the database must let other Python threads run. One that held the GIL
while waiting would stop the very thread holding the lock, and both would sit until the database's
10-second timeout (the desktop's saves timed out this way)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]

from backend import clock
from backend.storage import connect, initialize
from backend.tests.account_support import PASSWORD


def answer(database: Path, method: str, path: str, body: str = "", token: str = "") -> tuple:
    """One window request, as the desktop's client sends it (desktop/native/client.py)."""
    return flexweek_engine.service_answer(
        str(database), method, path, body, token, None, int(clock.seconds()), "2026-11-05T19:00", ""
    )


def test_a_window_request_waiting_for_the_write_lock_lets_the_holder_finish(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    initialize(database)
    made = answer(
        database, "POST", "/api/auth/register", f'{{"username": "alice", "password": "{PASSWORD}"}}'
    )
    assert made[0] == 201 and made[2] == "started", made
    token = made[3]
    locked = threading.Event()

    def hold_then_finish() -> None:
        with connect(database) as db:
            db.begin_immediate()
            locked.set()
            time.sleep(0.3)

    other = threading.Thread(target=hold_then_finish)
    other.start()
    assert locked.wait(5)
    started = time.monotonic()
    # Checking the session renews it, so the request needs the write lock the holder has.
    status, body, _, _ = answer(database, "GET", "/api/auth/me", token=token)
    waited = time.monotonic() - started
    other.join()
    assert status == 200 and '"alice"' in body
    assert waited < 5, f"the request held Python for {waited:.1f} s while it waited for the database"
