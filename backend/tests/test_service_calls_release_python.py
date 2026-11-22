"""A Rust service call that waits for the database must let other Python threads run, as the routes' own
store calls do. One that held the GIL while waiting would stop the very thread holding the lock, and both
would sit until the database's 10-second timeout (the desktop's saves timed out this way)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
from fastapi.testclient import TestClient

from backend import clock
from backend.app import COOKIE, create_app
from backend.storage import connect
from backend.tests.account_support import PASSWORD, WRITE


def test_a_service_call_waiting_for_the_write_lock_lets_the_holder_finish(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        made = client.post("/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE)
        assert made.status_code == 201, made.text
        token = client.cookies.get(COOKIE)
    assert token
    # The lock is taken through the store's own connection, as the routes take it: Python's sqlite3 module
    # carries another copy of SQLite, and in one process the two copies do not see each other's locks.
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
    # Checking the session renews it, so the call needs the write lock the holder has.
    found = flexweek_engine.service_signed_in(str(database), token, int(clock.seconds()))
    waited = time.monotonic() - started
    other.join()
    assert found[1] == "alice"
    assert waited < 5, f"the call held Python for {waited:.1f} s while it waited for the database"
