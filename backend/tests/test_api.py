"""HTTP checks for Phase 3: duration validation on POST /api/solve."""

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)

VALID_FLEX = {
    "id": "hw",
    "title": "Homework",
    "kind": "flexible",
    "duration_min": 60,
    "days": [0],
    "priority": 3,
    "energy": "medium",
}


def test_solve_rejects_duration_not_multiple_of_15() -> None:
    bad = {**VALID_FLEX, "duration_min": 10}
    response = client.post("/api/solve", json={"blocks": [bad]})
    assert response.status_code == 422


def test_solve_rejects_zero_duration() -> None:
    bad = {**VALID_FLEX, "duration_min": 0}
    response = client.post("/api/solve", json={"blocks": [bad]})
    assert response.status_code == 422


def test_solve_accepts_aligned_duration() -> None:
    response = client.post("/api/solve", json={"blocks": [VALID_FLEX]})
    assert response.status_code == 200
    body = response.json()
    assert "placed" in body
    assert "unplaced" in body
    assert "solve_ms" in body
