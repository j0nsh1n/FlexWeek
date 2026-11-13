"""A week on screen can start on any day. `GET /api/week` with a date that is not a Monday shows the
seven days from it, taken from the two stored (Monday) weeks it covers, and `POST /api/changes` splits
a saved one back. Its revision is the two stored weeks' revisions, first week first. Dates are read off
the 2026 calendar: Wednesday 11 November to Tuesday 17 November covers the weeks of Monday 9 and
Monday 16 November."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

PASSWORD = "a-long-test-password"
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
WED = "2026-11-11"
FIRST = "2026-11-09"
SECOND = "2026-11-16"
SCHOOL = [
    {
        "id": "school",
        "scope": "from",
        "from_date": "2026-11-02",
        "set": {"title": "School", "category": "class", "start": "08:30", "duration_min": 405},
        "add_days": [0, 1, 2, 3, 4],
    }
]


@pytest.fixture()
def alice(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(database=tmp_path / "shown.db", origin="http://testserver")) as client:
        made = client.post("/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE)
        assert made.status_code == 201, made.text
        yield client


def fixed(block_id: str, start: str, days: list[int]) -> dict:
    return {"id": block_id, "title": block_id, "kind": "locked", "duration_min": 60, "days": days, "start": start}


def week(client: TestClient, week_start: str) -> dict:
    response = client.get(f"/api/week?week_start={week_start}")
    assert response.status_code == 200, response.text
    return response.json()


def post(client: TestClient, body: dict) -> dict:
    response = client.post("/api/changes", json=body, headers=WRITE)
    assert response.status_code == 200, response.text
    return response.json()


def save(client: TestClient, week_start: str, blocks: list[dict], revision: object, **extra: object) -> dict:
    return post(client, {"weeks": [{"week_start": week_start, "blocks": blocks, "revision": revision}], **extra})


def days_of(blocks: list[dict]) -> dict[str, list[int]]:
    return {block["id"]: block["days"] for block in blocks}


def test_a_wednesday_week_nobody_saved_is_empty_with_both_revisions(alice: TestClient) -> None:
    shown = week(alice, WED)
    assert shown["week_start"] == WED
    assert shown["blocks"] == []
    assert shown["revision"] == [0, 0]


def test_a_thursday_block_is_stored_in_its_monday_week_and_a_monday_block_in_the_next(alice: TestClient) -> None:
    saved = save(alice, WED, [fixed("thu12", "10:00", [1]), fixed("mon16", "10:00", [5])], [0, 0])
    assert saved["weeks"][0]["week_start"] == WED
    assert saved["weeks"][0]["revision"] == [1, 1]
    assert days_of(week(alice, FIRST)["blocks"]) == {"thu12": [3]}
    assert days_of(week(alice, SECOND)["blocks"]) == {"mon16": [0]}
    shown = week(alice, WED)
    assert days_of(shown["blocks"]) == {"thu12": [1], "mon16": [5]}
    assert shown["revision"] == [1, 1]


def test_a_shown_week_change_on_one_side_leaves_the_other_stored_week_unwritten(alice: TestClient) -> None:
    save(alice, WED, [fixed("thu12", "10:00", [1])], [0, 0])
    assert week(alice, WED)["revision"] == [1, 0]
    assert week(alice, SECOND)["revision"] == 0


def test_a_repeat_deleted_from_the_shown_week_stays_on_the_days_before_and_after(alice: TestClient) -> None:
    gym = fixed("gym", "17:00", [0, 2, 4])
    save(alice, FIRST, [gym], 0)
    save(alice, SECOND, [gym], 0)
    shown = week(alice, WED)
    assert days_of(shown["blocks"]) == {"gym": [0, 2, 5]}
    save(alice, WED, [], shown["revision"])
    # Monday 9 is the week before's; Wednesday 18 and Friday 20 the week after's.
    assert days_of(week(alice, FIRST)["blocks"]) == {"gym": [0]}
    assert days_of(week(alice, SECOND)["blocks"]) == {"gym": [2, 4]}


def test_a_session_placed_after_the_seam_is_stored_once(alice: TestClient) -> None:
    waiting = {"id": "s1", "title": "Read", "kind": "flexible", "duration_min": 60, "days": [0, 1, 2, 3, 4, 5, 6]}
    save(alice, FIRST, [waiting], 0)
    shown = week(alice, WED)
    assert days_of(shown["blocks"]) == {"s1": [0, 1, 2, 3, 4]}
    placed = [{**shown["blocks"][0], "days": [5], "start": "16:00"}]
    save(alice, WED, placed, shown["revision"])
    assert week(alice, FIRST)["blocks"] == []
    stored = week(alice, SECOND)["blocks"]
    assert days_of(stored) == {"s1": [0]}
    assert stored[0]["start"] == "16:00"


def test_a_stale_revision_on_either_stored_week_refuses_the_whole_save(alice: TestClient) -> None:
    shown = week(alice, WED)
    # Another device saves the second week meanwhile.
    save(alice, SECOND, [fixed("phone", "12:00", [0])], 0)
    response = alice.post(
        "/api/changes",
        json={"weeks": [{"week_start": WED, "blocks": [fixed("thu12", "10:00", [1])], "revision": shown["revision"]}]},
        headers=WRITE,
    )
    assert response.status_code == 409
    # Nothing was written to the first week either.
    assert week(alice, FIRST)["blocks"] == []
    assert week(alice, FIRST)["revision"] == 0
    assert days_of(week(alice, WED)["blocks"]) == {"phone": [5]}


def test_a_retried_save_lands_once(alice: TestClient) -> None:
    body = {
        "weeks": [{"week_start": WED, "blocks": [fixed("mon16", "10:00", [5])], "revision": [0, 0]}],
        "operation_id": "op-1",
    }
    first = post(alice, body)
    again = post(alice, body)
    assert again == first
    assert week(alice, SECOND)["revision"] == 1
    assert days_of(week(alice, SECOND)["blocks"]) == {"mon16": [0]}


def test_a_monday_week_keeps_a_plain_revision(alice: TestClient) -> None:
    saved = save(alice, FIRST, [fixed("mon9", "10:00", [0])], 0)
    assert saved["weeks"][0]["revision"] == 1
    assert week(alice, FIRST)["revision"] == 1


def test_a_shown_revision_must_name_both_stored_weeks(alice: TestClient) -> None:
    for revision in (0, [0], [0, 0, 0]):
        response = alice.post(
            "/api/changes", json={"weeks": [{"week_start": WED, "blocks": [], "revision": revision}]}, headers=WRITE
        )
        assert response.status_code == 422, revision
    response = alice.post(
        "/api/changes", json={"weeks": [{"week_start": FIRST, "blocks": [], "revision": [0, 0]}]}, headers=WRITE
    )
    assert response.status_code == 422


def test_a_sunday_week_takes_its_sunday_from_the_week_before(alice: TestClient) -> None:
    save(alice, "2026-11-08", [fixed("sun8", "10:00", [0]), fixed("sat14", "10:00", [6])], [0, 0])
    assert days_of(week(alice, "2026-11-02")["blocks"]) == {"sun8": [6]}
    assert days_of(week(alice, FIRST)["blocks"]) == {"sat14": [5]}


def test_a_week_over_the_year_end_stores_its_january_days_in_january(alice: TestClient) -> None:
    # Wednesday 30 December 2026 to Tuesday 5 January 2027.
    save(alice, "2026-12-30", [fixed("dec31", "10:00", [1]), fixed("jan4", "10:00", [5])], [0, 0])
    assert days_of(week(alice, "2026-12-28")["blocks"]) == {"dec31": [3]}
    assert days_of(week(alice, "2027-01-04")["blocks"]) == {"jan4": [0]}
    # And one over a month end: Wednesday 25 November to Tuesday 1 December.
    save(alice, "2026-11-25", [fixed("dec1", "10:00", [6])], [0, 0])
    assert days_of(week(alice, "2026-11-30")["blocks"]) == {"dec1": [1]}


def test_school_taken_out_of_the_shown_week_and_later_stays_on_the_days_before(alice: TestClient) -> None:
    post(alice, {"weeks": [], "repeats": SCHOOL})
    shown = week(alice, WED)
    assert days_of(shown["blocks"]) == {"school": [0, 1, 2, 5, 6]}
    stop = [{"id": "school", "scope": "from", "from_date": WED, "stop": True}]
    save(alice, WED, [], shown["revision"], repeats=stop)
    # Monday 9 and Tuesday 10 belong to the week before the shown one and keep School.
    assert days_of(week(alice, FIRST)["blocks"]) == {"school": [0, 1]}
    assert week(alice, SECOND)["blocks"] == []
    assert week(alice, "2026-11-23")["blocks"] == []
    assert week(alice, "2026-11-02")["blocks"][0]["days"] == [0, 1, 2, 3, 4]


def test_school_taken_out_of_the_shown_week_only_is_missed_on_its_days_and_kept_on_the_others(
    alice: TestClient,
) -> None:
    post(alice, {"weeks": [], "repeats": SCHOOL})
    shown = week(alice, WED)
    school = shown["blocks"][0]
    save(alice, WED, [{**school, "missed_days": school["days"]}], shown["revision"])
    first = week(alice, FIRST)["blocks"][0]
    second = week(alice, SECOND)["blocks"][0]
    assert (first["days"], first["missed_days"]) == ([0, 1, 2, 3, 4], [2, 3, 4])
    assert (second["days"], second["missed_days"]) == ([0, 1, 2, 3, 4], [0, 1])
    assert "missed_days" not in week(alice, "2026-11-23")["blocks"][0]
