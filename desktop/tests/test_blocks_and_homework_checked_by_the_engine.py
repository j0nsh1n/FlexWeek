"""The window checks blocks and homework with the engine (engine/service/src/blocks.rs and homework_saves.rs),
not pydantic: through the binding, as JSON text, each case of the two parity corpora (made with the real
pydantic models) is refused where pydantic refused it and written exactly as pydantic wrote it. The homework
fields the window keeps are the model's."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.models import Assignment
from desktop.native.controller import HOMEWORK_FIELDS, _checked_block, _checked_homework

FIXTURES = Path(__file__).resolve().parents[2] / "engine/service/tests/fixtures"


def cases(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def check(checker, case: dict) -> object:
    try:
        return checker(case["input"])
    except ValueError:
        return None


@pytest.mark.parametrize(
    ("corpus", "checker", "least"),
    [("block_parity.json", _checked_block, 2000), ("homework_parity.json", _checked_homework, 1500)],
)
def test_every_corpus_case_is_checked_as_pydantic_checked_it(corpus: str, checker, least: int) -> None:
    every = cases(corpus)
    assert len(every) >= least, f"{corpus} shrank to {len(every)}"
    wrong = [case for case in every if json.dumps(check(checker, case)) != json.dumps(case["written"])]
    assert not wrong, f"{len(wrong)} differ, first: {wrong[0]}"


def test_a_refused_block_or_homework_raises_value_error() -> None:
    with pytest.raises(ValueError):
        _checked_block({"id": "", "title": "Club"})
    with pytest.raises(ValueError):
        _checked_homework({"id": "essay", "title": "Essay", "revision": 0})


def test_the_homework_fields_are_the_models() -> None:
    assert set(HOMEWORK_FIELDS) == set(Assignment.model_fields)
