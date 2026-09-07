import json
from pathlib import Path

from backend.models import TimeBlock
from backend.slots import hhmm_to_slot

DATA = Path(__file__).resolve().parent.parent / "data"


def load_blocks(name: str) -> list[TimeBlock]:
    raw = json.loads((DATA / name).read_text())
    return [TimeBlock.model_validate(item) for item in raw]


def all_blocks() -> list[TimeBlock]:
    blocks: list[TimeBlock] = []
    for name in ("demo_alex.json", "demo_jordan.json"):
        blocks.extend(load_blocks(name))
    return blocks


def test_demo_files_validate() -> None:
    for name in ("demo_alex.json", "demo_jordan.json"):
        blocks = load_blocks(name)
        assert any(block.kind == "locked" for block in blocks)
        assert any(block.kind == "flexible" for block in blocks)
        for block in blocks:
            if block.kind == "locked":
                assert block.start is not None


def test_each_demo_has_eight_flexible() -> None:
    for name in ("demo_alex.json", "demo_jordan.json"):
        blocks = load_blocks(name)
        flexible = [block for block in blocks if block.kind == "flexible"]
        assert len(flexible) == 8


def test_locked_starts_are_on_grid() -> None:
    for block in all_blocks():
        if block.kind != "locked":
            continue
        assert block.start is not None
        assert block.start != "23:00"
        assert hhmm_to_slot(block.start) >= 0


def test_durations_are_multiples_of_15() -> None:
    for block in all_blocks():
        assert block.duration_min > 0
        assert block.duration_min % 15 == 0
