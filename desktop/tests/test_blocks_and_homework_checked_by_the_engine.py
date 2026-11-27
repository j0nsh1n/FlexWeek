"""The window checks blocks and homework with the engine (engine/service/src/blocks.rs and homework_saves.rs):
through the binding, as JSON text, each case of the two parity corpora (frozen from the old pydantic models)
is refused where that model refused it and written exactly as that model wrote it. The homework fields the
window keeps are the engine's, in its order."""

from __future__ import annotations

import json
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

from desktop.native.controller import HOMEWORK_FIELDS, _checked_block, _checked_homework

# Assignment content in the engine's order (validate.rs ASSIGNMENT_FIELDS), then the save's revision.
HOMEWORK_FIELD_ORDER = (
    "id",
    "title",
    "course",
    "category",
    "priority",
    "energy",
    "spotify_url",
    "due",
    "estimate_min",
    "spread",
    "focus_minutes",
    "focus_sessions",
    "completed",
    "completed_at",
    "notes",
    "links",
    "checklist",
    "revision",
)

FIXTURES = Path(__file__).resolve().parents[2] / "engine/service/tests/fixtures"


def cases(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def check(checker, case: dict) -> object:
    try:
        return checker(case["input"])
    except ValueError:
        return None


@pytest.mark.parametrize(
    ("corpus", "checker", "least", "kept"),
    [
        ("block_parity.json", _checked_block, 2000, 400),
        ("homework_parity.json", _checked_homework, 1500, 400),
    ],
)
def test_every_corpus_case_is_checked_as_pydantic_checked_it(
    corpus: str, checker, least: int, kept: int
) -> None:
    every = cases(corpus)
    assert len(every) >= least, f"{corpus} shrank to {len(every)}"
    accepted = sum(1 for case in every if case["written"] is not None)
    assert accepted >= kept, f"only {accepted} cases of {corpus} are accepted"
    wrong = [case for case in every if json.dumps(check(checker, case)) != json.dumps(case["written"])]
    assert not wrong, f"{len(wrong)} differ, first: {wrong[0]}"


def test_a_refused_block_or_homework_raises_value_error() -> None:
    with pytest.raises(ValueError):
        _checked_block({"id": "", "title": "Club"})
    with pytest.raises(ValueError):
        _checked_homework({"id": "essay", "title": "Essay", "revision": 0})


def test_the_homework_fields_follow_the_engine() -> None:
    assert flexweek_engine.homework_fields() == list(HOMEWORK_FIELD_ORDER)
    assert set(HOMEWORK_FIELDS) == set(HOMEWORK_FIELD_ORDER)
