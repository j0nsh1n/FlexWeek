"""HTTP checks for Phase 3: duration validation on POST /api/solve."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}

VALID_FLEX = {
    "id": "hw",
    "title": "Homework",
    "kind": "flexible",
    "duration_min": 60,
    "days": [0],
    "priority": 3,
    "energy": "medium",
}


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(database: Path) -> FastAPI:
    return create_app(database=database, origin="http://testserver")


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def account(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    return client


def test_solve_rejects_duration_not_multiple_of_15(account: TestClient) -> None:
    bad = {**VALID_FLEX, "duration_min": 10}
    response = account.post("/api/solve", json={"blocks": [bad]}, headers=WRITE)
    assert response.status_code == 422


def test_solve_rejects_zero_duration(account: TestClient) -> None:
    bad = {**VALID_FLEX, "duration_min": 0}
    response = account.post("/api/solve", json={"blocks": [bad]}, headers=WRITE)
    assert response.status_code == 422


def test_solve_accepts_aligned_duration(account: TestClient) -> None:
    response = account.post("/api/solve", json={"blocks": [VALID_FLEX]}, headers=WRITE)
    assert response.status_code == 200
    body = response.json()
    assert "placed" in body
    assert "unplaced" in body
    assert "solve_ms" in body
