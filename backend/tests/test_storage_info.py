"""The storage status the app shows: on this device or on a hosted server, who is signed in, and the transfer limit."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.tests.account_support import HOSTED_WRITE, PASSWORD, WRITE


def test_storage_info_names_the_account_and_origin_but_never_the_database_path(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    with TestClient(create_app(database=database, origin="http://testserver")) as client:
        registered = client.post(
            "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
        )
        assert registered.status_code == 201, registered.text
        response = client.get("/api/storage-info")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "mode": "local",
            "label": "On this device",
            "username": "alice",
            "origin": "http://testserver",
            "transfer_limit_bytes": 262144,
        }
        assert "test.db" not in response.text
        assert str(database) not in response.text


def test_storage_info_is_hosted_on_a_public_origin(tmp_path: Path) -> None:
    app = create_app(database=tmp_path / "hosted.db", origin="https://flexweek.example")
    with TestClient(app, base_url="https://flexweek.example") as client:
        assert (
            client.post(
                "/api/auth/register",
                json={"username": "alice", "password": PASSWORD},
                headers=HOSTED_WRITE,
            ).status_code
            == 201
        )
        response = client.get("/api/storage-info")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "mode": "hosted",
            "label": "On your FlexWeek server",
            "username": "alice",
            "origin": "https://flexweek.example",
            "transfer_limit_bytes": 262144,
        }
