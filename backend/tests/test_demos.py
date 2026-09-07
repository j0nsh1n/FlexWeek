import json
from pathlib import Path

from backend.models import TimeBlock

DATA = Path(__file__).resolve().parent.parent / "data"


def test_demo_files_validate() -> None:
    for name in ("demo_alex.json", "demo_jordan.json"):
        raw = json.loads((DATA / name).read_text())
        blocks = [TimeBlock.model_validate(item) for item in raw]
        assert any(block.kind == "locked" for block in blocks)
        assert any(block.kind == "flexible" for block in blocks)
        for block in blocks:
            if block.kind == "locked":
                assert block.start is not None
