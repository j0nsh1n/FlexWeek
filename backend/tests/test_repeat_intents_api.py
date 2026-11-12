"""Changes to School and Setup's activities through `POST /api/changes`, checked by what each week shows
in `GET /api/week`. The cases and their answers are the ones the Rust save handler runs
(`engine/store/tests/fixtures/repeat_cases.json`), worked out by hand from the owner's rules, so the two
handlers cannot drift apart unnoticed."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "engine/store/tests/fixtures/repeat_cases.json").read_text()
)


@pytest.fixture()
def alice(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(database=tmp_path / "repeats.db", origin="http://testserver")) as client:
        made = client.post("/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE)
        assert made.status_code == 201, made.text
        yield client


def changes(client: TestClient, body: dict) -> dict:
    response = client.post("/api/changes", json=body, headers=WRITE)
    assert response.status_code == 200, response.text
    return response.json()


def week(client: TestClient, week_start: str) -> dict:
    response = client.get(f"/api/week?week_start={week_start}")
    assert response.status_code == 200, response.text
    return response.json()


def summary(blocks: list[dict]) -> dict:
    return {
        b["id"]: [b["title"], b["start"], b["duration_min"], b["days"], b.get("missed_days") or []] for b in blocks
    }


def set_clock(client: TestClient, clock_24h: bool) -> None:
    preferences = client.get("/api/preferences").json()
    preferences["clock_24h"] = clock_24h
    saved = client.put("/api/preferences", json=preferences, headers=WRITE)
    assert saved.status_code == 200, saved.text


@pytest.mark.parametrize("case", CASES["cases"], ids=[case["name"] for case in CASES["cases"]])
def test_a_shared_case_gives_the_answer_worked_out_for_both_save_handlers(alice: TestClient, case: dict) -> None:
    set_clock(alice, case["clock_24h"])
    changes(alice, {"weeks": [], "repeats": CASES["setup"]})
    last: dict = {}
    for step in case["steps"]:
        weeks = [
            {
                "week_start": entry["week_start"],
                "blocks": [CASES[block] if isinstance(block, str) else block for block in entry["blocks"]],
                "revision": week(alice, entry["week_start"])["revision"],
            }
            for entry in step.get("weeks", [])
        ]
        body: dict = {"weeks": weeks}
        if "repeats" in step:
            body["repeats"] = step["repeats"]
        last = changes(alice, body)
    assert last["repeats"] == case["answer_repeats"]
    for week_start, expected in case["shown"].items():
        assert summary(week(alice, week_start)["blocks"]) == expected, week_start


def test_the_week_names_the_repeats_as_they_stand_in_it(alice: TestClient) -> None:
    changes(alice, {"weeks": [], "repeats": CASES["setup"]})
    changes(
        alice,
        {"repeats": [{"id": "school", "scope": "from", "from_date": "2026-11-16", "set": {"duration_min": 360}}]},
    )
    assert "repeats" not in week(alice, "2026-10-26")
    assert week(alice, "2026-11-09")["repeats"] == [CASES["school"], CASES["soccer"]]
    assert week(alice, "2026-11-16")["repeats"] == [{**CASES["school"], "duration_min": 360}, CASES["soccer"]]


def test_a_change_that_is_not_one_is_refused_with_its_sentence_and_saves_nothing(alice: TestClient) -> None:
    changes(alice, {"weeks": [], "repeats": CASES["setup"]})
    empties = {"id": "activity-1", "scope": "from", "from_date": "2026-11-09", "remove_days": [1, 3]}
    refused = alice.post(
        "/api/changes",
        json={"weeks": [{"week_start": "2026-11-09", "blocks": [CASES["school"]], "revision": 0}], "repeats": [empties]},
        headers=WRITE,
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == (
        "That change leaves no day, so nothing changed. Use stop to take it off the calendar."
    )
    shown = week(alice, "2026-11-09")
    assert shown["revision"] == 0
    assert [b["id"] for b in shown["blocks"]] == ["school", "activity-1"]


def test_a_replayed_batch_gets_the_first_answer(alice: TestClient) -> None:
    changes(alice, {"weeks": [], "repeats": CASES["setup"]})
    later = {**CASES["school"], "days": [0, 1, 3, 4]}
    changes(alice, {"weeks": [{"week_start": "2026-11-16", "blocks": [later, CASES["soccer"]], "revision": 0}]})
    body = {
        "weeks": [],
        "operation_id": "op-school-hours",
        "repeats": [{"id": "school", "scope": "from", "from_date": "2026-11-09", "set": {"duration_min": 360}}],
    }
    first = changes(alice, body)
    revision = week(alice, "2026-11-16")["revision"]
    assert changes(alice, body) == first
    assert week(alice, "2026-11-16")["revision"] == revision
