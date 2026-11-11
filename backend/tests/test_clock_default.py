"""The clock is 12-hour for a new account, and 24-hour for every account that never chose before the clock choice existed.

A 24-hour clock used to be the default and was never stored, so "never chose" and "new" looked the same.
The update stamps 24-hour onto each existing account once.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import TransferSnapshot, create_app
from backend.storage import initialize

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}


def client_for(database: Path) -> TestClient:
    return TestClient(create_app(database=database, origin="http://testserver"))


def register(client: TestClient, username: str) -> None:
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD}, headers=WRITE)
    assert response.status_code == 201, response.text


def log_in(client: TestClient, username: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD}, headers=WRITE)
    assert response.status_code == 200, response.text


def clock_of(client: TestClient) -> bool:
    """A 12-hour clock is the default, so it is left off the wire."""
    return client.get("/api/preferences").json().get("clock_24h", False)


def save_clock(client: TestClient, on: bool) -> None:
    prefs = client.get("/api/preferences").json()
    saved = client.put("/api/preferences", json={**prefs, "clock_24h": on}, headers=WRITE)
    assert saved.status_code == 200, saved.text


def as_saved_before_the_clock_choice(database: Path, username: str, comfort: dict | None) -> None:
    """Put the account back as the previous version left it: version 1, and a comfort text that only
    holds the clock when the student had saved Settings (which writes every comfort key)."""
    with sqlite3.connect(database) as db:
        db.execute(
            "UPDATE preferences SET prefs_version = 1, comfort_json = ? "
            "WHERE user_id = (SELECT id FROM users WHERE username = ?)",
            (json.dumps(comfort if comfort is not None else {}), username),
        )


def test_a_new_account_has_a_12_hour_clock(tmp_path: Path) -> None:
    with client_for(tmp_path / "new.db") as client:
        register(client, "fresh")
        assert clock_of(client) is False


def test_a_choice_of_24_hour_and_back_sticks(tmp_path: Path) -> None:
    with client_for(tmp_path / "choice.db") as client:
        register(client, "chooser")
        save_clock(client, True)
        assert clock_of(client) is True
        save_clock(client, False)
        assert clock_of(client) is False


def test_an_account_that_never_chose_before_the_update_keeps_24_hour(tmp_path: Path) -> None:
    database = tmp_path / "old.db"
    with client_for(database) as client:
        register(client, "veteran")
    as_saved_before_the_clock_choice(database, "veteran", None)

    initialize(database)

    with client_for(database) as client:
        log_in(client, "veteran")
        assert clock_of(client) is True


def test_an_old_account_that_chose_12_hour_keeps_it_and_the_stamp_is_applied_once(tmp_path: Path) -> None:
    database = tmp_path / "chose.db"
    with client_for(database) as client:
        register(client, "twelve")
        client.post("/api/auth/logout", headers=WRITE)
        register(client, "never")
    as_saved_before_the_clock_choice(database, "twelve", {"clock_24h": False, "end_chime": True})
    as_saved_before_the_clock_choice(database, "never", None)

    initialize(database)
    initialize(database)

    with client_for(database) as client:
        log_in(client, "twelve")
        assert clock_of(client) is False
        client.post("/api/auth/logout", headers=WRITE)
        log_in(client, "never")
        assert clock_of(client) is True
        # A choice made after the update is not undone by the next start.
        save_clock(client, False)
    initialize(database)
    with client_for(database) as client:
        log_in(client, "never")
        assert clock_of(client) is False


def test_a_snapshot_exported_before_the_update_without_a_clock_reads_24_hour() -> None:
    """The old build left a 24-hour clock out of its export file, as it did off the wire."""
    snapshot = {
        "format": 3,
        "exported_at": "2026-10-01T09:00",
        "username": "veteran",
        "weeks": [],
        "assignments": [],
        "preferences": {"theme": "system"},
        "routines": [],
    }
    assert TransferSnapshot.model_validate(snapshot).preferences.clock_24h is True
    twelve = {**snapshot, "preferences": {"theme": "system", "clock_24h": False}}
    assert TransferSnapshot.model_validate(twelve).preferences.clock_24h is False


def test_an_export_always_says_the_clock_so_a_12_hour_file_is_not_read_as_old(tmp_path: Path) -> None:
    with client_for(tmp_path / "export.db") as client:
        register(client, "exporter")
        exported = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE).json()
        assert exported["preferences"]["clock_24h"] is False
        assert TransferSnapshot.model_validate(exported).preferences.clock_24h is False
        save_clock(client, True)
        exported = client.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE).json()
        assert exported["preferences"]["clock_24h"] is True


def step_of(client: TestClient) -> int:
    """15 minutes is the default, so it is left off the wire."""
    return client.get("/api/preferences").json().get("drag_step_min", 15)


def test_an_older_account_whose_saved_settings_hold_a_5_minute_step_moves_to_15_once(tmp_path: Path) -> None:
    """Before the 15-minute default, saving any setting wrote a 5-minute step down, chosen or not. The
    update moves each stored 5 to 15 once; picking 5 in Settings afterwards sticks through a restart."""
    database = tmp_path / "old-step.db"
    with client_for(database) as client:
        register(client, "saver")
    with sqlite3.connect(database) as db:
        db.execute(
            "UPDATE preferences SET prefs_version = 4, comfort_json = ? "
            "WHERE user_id = (SELECT id FROM users WHERE username = ?)",
            (json.dumps({"end_chime": True, "drag_step_min": 5}), "saver"),
        )
    with client_for(database) as client:
        log_in(client, "saver")
        assert step_of(client) == 15
        assert client.get("/api/preferences").json()["end_chime"] is True
        prefs = client.get("/api/preferences").json()
        saved = client.put("/api/preferences", json={**prefs, "drag_step_min": 5}, headers=WRITE)
        assert saved.status_code == 200, saved.text
    with client_for(database) as client:
        log_in(client, "saver")
        assert step_of(client) == 5
