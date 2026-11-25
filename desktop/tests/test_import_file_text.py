"""A week or day file whose text is not real Unicode is refused with words, not a crash (review of #181:
pydantic used to refuse a lone surrogate; the engine's checks took over in slice 9A)."""

from __future__ import annotations

import json

from desktop.native.files import export_week_payload, parse_import_payload

WEEK = "2026-11-23"
HOMEWORK = {
    "id": "essay",
    "title": "History essay",
    "due": "2026-11-26T23:59",
    "estimate_min": 60,
}
BLOCK = {
    "id": "s1",
    "title": "History essay",
    "kind": "flexible",
    "days": [2],
    "start": "18:00",
    "duration_min": 60,
    "assignment_id": "essay",
}


def _file(title: str, block_title: str = "History essay") -> str:
    payload = export_week_payload(WEEK, [BLOCK], {"essay": HOMEWORK})
    payload["assignments"][0]["title"] = title
    payload["blocks"][0]["title"] = block_title
    return json.dumps(payload)


def test_a_homework_title_with_a_lone_surrogate_is_refused_with_words() -> None:
    answer = parse_import_payload(_file("\udc00"))
    assert answer == {"error": "The file has text that can't be read. Nothing was imported."}


def test_a_block_title_with_a_lone_surrogate_is_refused_with_words() -> None:
    answer = parse_import_payload(_file("History essay", block_title="\udc00"))
    assert answer == {"error": "The file has text that can't be read. Nothing was imported."}


def test_a_title_with_a_character_outside_the_basic_plane_imports() -> None:
    answer = parse_import_payload(_file("Essay \U0001f4da"))
    assert answer.get("error") is None
    assert [item["title"] for item in answer["assignments"]] == ["Essay \U0001f4da"]
