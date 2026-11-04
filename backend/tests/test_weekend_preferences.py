"""The week display preference is a planner column. Default on is omitted. Comfort is not a store."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}


def _column(database: Path) -> int:
    with sqlite3.connect(database) as db:
        return int(db.execute("SELECT show_weekends FROM preferences").fetchone()[0])


def _comfort(database: Path) -> dict:
    with sqlite3.connect(database) as db:
        raw = db.execute("SELECT comfort_json FROM preferences").fetchone()[0]
    return json.loads(raw)


def test_weekends_round_trip_and_invalid_write_keeps_the_saved_choice(tmp_path: Path) -> None:
    database = tmp_path / "preferences.db"
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "a-long-test-password"},
            headers=WRITE,
        )
        assert registered.status_code == 201
        defaults = client.get("/api/preferences").json()
        assert "show_weekends" not in defaults
        assert _column(database) == 1

        saved = client.put("/api/preferences", json={**defaults, "show_weekends": False}, headers=WRITE)
        assert saved.status_code == 200
        assert saved.json()["show_weekends"] is False
        assert client.get("/api/preferences").json()["show_weekends"] is False
        assert _column(database) == 0
        assert "show_weekends" not in _comfort(database)

        refused = client.put("/api/preferences", json={**defaults, "show_weekends": []}, headers=WRITE)
        assert refused.status_code == 422
        assert client.get("/api/preferences").json()["show_weekends"] is False
        assert _column(database) == 0

        restored = client.put("/api/preferences", json={**defaults, "show_weekends": True}, headers=WRITE)
        assert restored.status_code == 200
        assert "show_weekends" not in restored.json()
        assert "show_weekends" not in client.get("/api/preferences").json()
        assert _column(database) == 1
        assert "show_weekends" not in _comfort(database)


@pytest.mark.parametrize("invalid", [None, 0, "false", [], {}])
def test_comfort_weekend_values_do_not_override_the_column(tmp_path: Path, invalid: object) -> None:
    database = tmp_path / "preferences.db"
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "a-long-test-password"},
            headers=WRITE,
        )
        assert registered.status_code == 201
        with sqlite3.connect(database) as db:
            db.execute(
                "UPDATE preferences SET comfort_json = ?",
                (json.dumps({"show_weekends": invalid}),),
            )
        response = client.get("/api/preferences")
        assert response.status_code == 200
        assert "show_weekends" not in response.json()
        assert _column(database) == 1


def test_the_column_hides_weekends_even_if_comfort_says_otherwise(tmp_path: Path) -> None:
    database = tmp_path / "preferences.db"
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "a-long-test-password"},
            headers=WRITE,
        )
        assert registered.status_code == 201
        with sqlite3.connect(database) as db:
            db.execute(
                "UPDATE preferences SET show_weekends = 0, comfort_json = ?",
                (json.dumps({"show_weekends": True}),),
            )
        assert client.get("/api/preferences").json()["show_weekends"] is False
        assert _column(database) == 0
