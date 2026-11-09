"""An assignment's notes, links and checklist: saved, returned, left off the wire when empty, and refused when unsafe."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import create_app
from backend.models import Assignment

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WEEK = "2026-09-14"


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
def alice(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    return client


def assignment(**overrides) -> dict:
    body = {
        "id": "hw-essay",
        "title": "Essay",
        "course": "History",
        "category": None,
        "priority": 2,
        "energy": "low",
        "spotify_url": None,
        "due": "2026-09-15T23:59",
        "estimate_min": 120,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": 0,
    }
    body.update(overrides)
    return body


def test_assignment_notes_round_trip_over_http(alice: TestClient) -> None:
    payload = assignment(
        notes="Bring the outline.",
        links=[{"label": "Prompt", "url": "https://example.edu/essay"}],
        checklist=[{"id": "draft", "text": "First draft", "done": True}],
    )
    saved = alice.put("/api/assignments/hw-essay", json=payload, headers=WRITE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["notes"] == "Bring the outline."
    assert saved.json()["links"] == [{"label": "Prompt", "url": "https://example.edu/essay"}]
    assert saved.json()["checklist"] == [{"id": "draft", "text": "First draft", "done": True}]
    loaded = alice.get(f"/api/assignments?week_start={WEEK}").json()["assignments"][0]
    assert loaded["notes"] == "Bring the outline."
    assert loaded["links"] == [{"label": "Prompt", "url": "https://example.edu/essay"}]
    assert loaded["checklist"] == [{"id": "draft", "text": "First draft", "done": True}]
    rejected = alice.put(
        "/api/assignments/hw-essay",
        json=assignment(revision=1, links=[{"label": "Bad", "url": "javascript:alert(1)"}]),
        headers=WRITE,
    )
    assert rejected.status_code == 422


def test_assignment_notes_links_and_checklist_round_trip_and_omit_empties() -> None:
    empty = Assignment.model_validate(
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-09-15T23:59",
            "estimate_min": 120,
            "revision": 0,
        }
    )
    dumped = empty.model_dump()
    assert "notes" not in dumped
    assert "links" not in dumped
    assert "checklist" not in dumped
    filled = Assignment.model_validate(
        {
            "id": "hw-essay",
            "title": "Essay",
            "due": "2026-09-15T23:59",
            "estimate_min": 120,
            "revision": 1,
            "notes": "Use the primary sources from week 3.",
            "links": [{"label": "Prompt", "url": "https://example.edu/prompt"}],
            "checklist": [{"id": "outline", "text": "Outline", "done": False}],
        }
    )
    assert filled.model_dump()["notes"] == "Use the primary sources from week 3."
    assert filled.model_dump()["links"] == [{"label": "Prompt", "url": "https://example.edu/prompt"}]
    assert filled.model_dump()["checklist"] == [{"id": "outline", "text": "Outline", "done": False}]


def test_assignment_rejects_javascript_urls_and_duplicate_checklist_ids() -> None:
    base = {
        "id": "hw-essay",
        "title": "Essay",
        "due": "2026-09-15T23:59",
        "estimate_min": 120,
        "revision": 0,
    }
    with pytest.raises(ValidationError):
        Assignment.model_validate({**base, "links": [{"label": "Bad", "url": "javascript:alert(1)"}]})
    with pytest.raises(ValidationError):
        Assignment.model_validate(
            {
                **base,
                "checklist": [
                    {"id": "one", "text": "First"},
                    {"id": "one", "text": "Again"},
                ],
            }
        )
