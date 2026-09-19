"""Week and day file parse/merge. Expected values match frontend export rules."""

from __future__ import annotations

import json

from desktop.native.files import (
    EXPORT_VERSION,
    export_day_payload,
    export_week_payload,
    merge_imported_blocks,
    parse_import_payload,
    plan_imported_homework,
)


def soccer() -> dict:
    return {
        "id": "soccer",
        "title": "Soccer",
        "kind": "locked",
        "duration_min": 60,
        "days": [0, 2],
        "start": "16:00",
        "category": "exercise",
    }


def essay() -> dict:
    return {
        "id": "essay",
        "title": "Essay",
        "due": "2026-09-18T21:00",
        "estimate_min": 60,
        "priority": 3,
        "energy": "medium",
        "completed": False,
    }


def test_week_export_carries_referenced_homework_and_drops_unknown_links() -> None:
    session = {
        "id": "sess",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0, 1, 2, 3, 4],
        "assignment_id": "essay",
    }
    orphan = {**soccer(), "assignment_id": "missing"}
    payload = export_week_payload("2026-09-14", [session, orphan], {"essay": essay()})
    assert payload["format"] == "flexweek-week"
    assert payload["version"] == EXPORT_VERSION
    assert payload["assignments"][0]["id"] == "essay"
    assert "assignment_id" not in payload["blocks"][1]


def test_parse_rejects_newer_versions_and_plain_text() -> None:
    assert parse_import_payload("")["error"] == "Empty file."
    assert "JSON" in parse_import_payload("not json")["error"]
    newer = json.dumps({"format": "flexweek-week", "version": 99, "blocks": []})
    assert "newer FlexWeek" in parse_import_payload(newer)["error"]


def test_day_import_splits_a_locked_series_instead_of_replacing_other_days() -> None:
    existing = [soccer()]
    incoming = [{**soccer(), "days": [0], "start": "17:00"}]
    merged = merge_imported_blocks(existing, incoming, "merge", 0)
    by_id = {block["id"]: block for block in merged}
    assert by_id["soccer"]["days"] == [2]
    assert by_id["soccer"]["start"] == "16:00"
    split = by_id["occ-0-soccer"]
    assert split["days"] == [0]
    assert split["start"] == "17:00"


def test_plan_imported_homework_reuses_matching_ids_and_migrates_the_rest() -> None:
    own = essay()
    other = {**essay(), "id": "other", "title": "Lab"}
    plan = plan_imported_homework(
        [own, other],
        [
            {"id": "a", "assignment_id": "essay"},
            {"id": "b", "assignment_id": "other"},
        ],
        "2026-09-14",
        {"essay": own},
    )
    assert plan["blocks"][0]["assignment_id"] == "essay"
    assert plan["blocks"][1]["assignment_id"].startswith("a-")
    assert plan["create"][0]["id"] == plan["blocks"][1]["assignment_id"]


def test_replace_mode_drops_existing_blocks() -> None:
    merged = merge_imported_blocks([soccer()], [{**soccer(), "id": "band"}], "replace", None)
    assert [block["id"] for block in merged] == ["band"]


def test_parse_rejects_oversize_dangling_and_pomodoro_pairs() -> None:
    too_many = [{**soccer(), "id": f"b{index}"} for index in range(101)]
    packed = json.dumps(
        {
            "format": "flexweek-week",
            "version": 2,
            "week_start": "2026-09-14",
            "blocks": too_many,
            "assignments": [],
        }
    )
    assert "more than 100 blocks" in parse_import_payload(packed)["error"]
    session = {
        "id": "sess",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "assignment_id": "essay",
    }
    dangling = json.dumps(
        {
            "format": "flexweek-week",
            "version": 2,
            "week_start": "2026-09-14",
            "blocks": [session],
            "assignments": [],
        }
    )
    assert "does not include" in parse_import_payload(dangling)["error"]
    repeated = json.dumps(
        {
            "format": "flexweek-week",
            "version": 2,
            "week_start": "2026-09-14",
            "blocks": [],
            "assignments": [essay(), essay()],
        }
    )
    assert "homework id" in parse_import_payload(repeated)["error"]
    chunk = {**soccer(), "id": "chunk", "pomodoro_parent_id": "soccer", "pomodoro_role": "work"}
    paired = json.dumps(
        {
            "format": "flexweek-week",
            "version": 2,
            "week_start": "2026-09-14",
            "blocks": [soccer(), chunk],
            "assignments": [],
        }
    )
    assert "focus chunks" in parse_import_payload(paired)["error"]


def test_day_export_completed_flexible_pins_to_completed_day() -> None:
    session = {
        "id": "sess",
        "title": "Essay",
        "kind": "flexible",
        "duration_min": 60,
        "days": [1, 3],
        "start": "16:00",
        "completed": True,
        "completed_day": 3,
        "assignment_id": "essay",
    }
    tuesday = export_day_payload("2026-09-14", 1, [session], {"essay": essay()})
    thursday = export_day_payload("2026-09-14", 3, [session], {"essay": essay()})
    assert tuesday["blocks"] == []
    assert [block["id"] for block in thursday["blocks"]] == ["sess"]
    assert thursday["blocks"][0]["days"] == [3]


def test_day_export_keeps_only_that_weekday() -> None:
    payload = export_day_payload("2026-09-14", 0, [soccer()], {})
    assert payload["format"] == "flexweek-day"
    assert payload["day"] == 0
    assert payload["blocks"][0]["days"] == [0]
    parsed = parse_import_payload(json.dumps(payload))
    assert parsed.get("error") is None
    assert parsed["day"] == 0
