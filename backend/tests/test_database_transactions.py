"""That a held write lock makes the next request wait without freezing other Python threads. (What a failed
write leaves behind and what BEGIN IMMEDIATE does moved to engine/service/tests/database_transactions.rs.)"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

from backend.storage import initialize, throttle


def test_a_held_write_lock_makes_throttle_wait(tmp_path: Path) -> None:
    """SQLite's busy wait runs on the real clock, so this one test measures real elapsed time
    (time.monotonic, which the fake clock does not own). While throttle waits, another Python thread
    has to keep running: the wait must not hold the GIL."""
    path = tmp_path / "lock.db"
    initialize(path)
    holder = flexweek_engine.open_connection(str(path))
    holder.execute("BEGIN IMMEDIATE")
    stop = threading.Event()
    beats = {"count": 0}

    def beat() -> None:
        while not stop.is_set():
            beats["count"] += 1

    thread = threading.Thread(target=beat)
    thread.start()
    started = time.monotonic()
    with pytest.raises(sqlite3.OperationalError):
        throttle(path, "10.0.0.1", "ada")
    waited = time.monotonic() - started
    stop.set()
    thread.join()
    holder.rollback()
    holder.close()
    assert waited >= 5
    assert beats["count"] >= 10
