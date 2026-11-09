"""What a failed write leaves behind (nothing), what BEGIN IMMEDIATE does, and that a held write lock
makes the next request wait without freezing other threads."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

from backend.storage import connect, initialize, throttle


def test_a_register_that_fails_part_way_leaves_no_account(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import backend.app as app_module

    path = tmp_path / "accounts.db"
    app = app_module.create_app(database=path, origin="http://testserver")

    def boom(*args, **kwargs):
        raise RuntimeError("recovery codes failed")

    monkeypatch.setattr(app_module, "replace_recovery_codes", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "ada", "password": "a-long-test-password"},
            headers={"Origin": "http://testserver", "X-FlexWeek-Request": "1"},
        )
    assert response.status_code == 500, response.text
    check = sqlite3.connect(path)
    assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0, "a user row was left behind"
    assert check.execute("SELECT COUNT(*) FROM preferences").fetchone()[0] == 0
    check.close()


def test_a_failed_later_write_rolls_the_earlier_ones_back(tmp_path: Path) -> None:
    path = tmp_path / "reg.db"
    with connect(path) as db:
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
    with pytest.raises(sqlite3.IntegrityError), connect(path) as db:
        db.execute("INSERT INTO users(name) VALUES ('a')")
        db.execute("INSERT INTO users(name) VALUES ('b')")
        db.execute("INSERT INTO users(name) VALUES ('a')")
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0


def test_begin_immediate_commits_or_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "tx.db"
    with connect(path) as db:
        db.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO t(name) VALUES ('kept')")
    with connect(path) as db:
        assert db.execute("SELECT name FROM t").fetchone()["name"] == "kept"
    with pytest.raises(sqlite3.IntegrityError), connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO t(id, name) VALUES (1, 'x')")
        db.execute("INSERT INTO t(id, name) VALUES (1, 'y')")
    with connect(path) as db:
        names = [row["name"] for row in db.execute("SELECT name FROM t")]
    assert names == ["kept"]


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
