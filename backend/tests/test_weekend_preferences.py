"""The week display preference survives the API and keeps its default."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}


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

        saved = client.put("/api/preferences", json={**defaults, "show_weekends": False}, headers=WRITE)
        assert saved.status_code == 200
        assert saved.json()["show_weekends"] is False
        assert client.get("/api/preferences").json()["show_weekends"] is False

        refused = client.put("/api/preferences", json={**defaults, "show_weekends": []}, headers=WRITE)
        assert refused.status_code == 422
        assert client.get("/api/preferences").json()["show_weekends"] is False

        restored = client.put("/api/preferences", json={**defaults, "show_weekends": True}, headers=WRITE)
        assert restored.status_code == 200
        assert "show_weekends" not in restored.json()
        assert "show_weekends" not in client.get("/api/preferences").json()
        with sqlite3.connect(database) as db:
            comfort = json.loads(db.execute("SELECT comfort_json FROM preferences").fetchone()[0])
        assert "show_weekends" not in comfort


@pytest.mark.parametrize("invalid", [None, 0, "false", [], {}])
def test_invalid_stored_weekend_value_uses_the_default(tmp_path: Path, invalid: object) -> None:
    database = tmp_path / "preferences.db"
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "a-long-test-password"},
            headers=WRITE,
        )
        assert registered.status_code == 201
        with sqlite3.connect(database) as db:
            db.execute("UPDATE preferences SET comfort_json = ?", (json.dumps({"show_weekends": invalid}),))
        response = client.get("/api/preferences")
        assert response.status_code == 200
        assert "show_weekends" not in response.json()
