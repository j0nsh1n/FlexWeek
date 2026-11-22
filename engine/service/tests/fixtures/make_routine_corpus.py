"""The routine save parity corpus: generated routine saves and what pydantic's Routine makes of each (the
written routine, or a refusal). Fixed seed, so the corpus is the same on every run. Run with the project venv
from the repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 1500."""

import json
import random
import sys

from backend.models import Routine

rng = random.Random(20261122)
STARTS = ["08:00", "16:30", "23:45", "24:00", "8:00", "0٩:00", "", "x", None, 800]
DURATIONS = [30, 60, 390, 0, -15, 7140, 7141, " 60", "60.0", 60.0, 60.5, True, None]
DAYS = [[0], [0, 1, 2, 3, 4], [], [0, 0], [7], ["1"], [1.0], [True], None]
NAMES = ["School week", "  ", "\x1f", "x" * 80, "x" * 81, "", 5, None]
BLOCK_EXTRAS = {
    "category": [None, "School", "x" * 33, 3], "course": [None, "Math", "x" * 41],
    "priority": [1, 4, 0, 2.0, True, "2", None], "energy": ["high", "low", "HIGH", None],
    "spotify_url": [None, "", "https://open.spotify.com/track/abc", "http://x"], "extra": [1],
}

# Values the model accepts, so most saves reach how the routine is written.
GOOD = {
    "category": [None, "School"], "course": [None, "Math"], "priority": [1, 4, 2.0, True],
    "energy": ["high", "low"], "spotify_url": [None, "", "https://open.spotify.com/track/abc"], "extra": [1],
}


def block(index: int) -> dict:
    item: dict = {"template_id": f"t{index}", "title": "School", "days": [index % 7],
                  "start": f"{8 + 2 * index:02d}:00", "duration_min": 60}  # fmt: skip
    if rng.random() < 0.15:
        name, pool = rng.choice([("start", STARTS), ("duration_min", DURATIONS), ("days", DAYS),
                                 ("title", NAMES), ("template_id", ["", "x" * 81, 5])])  # fmt: skip
        value = rng.choice(pool)
        if value is None and rng.random() < 0.5:
            item.pop(name)
        else:
            item[name] = value
    for name, pool in BLOCK_EXTRAS.items():
        if rng.random() < 0.08:
            item[name] = rng.choice(GOOD[name]) if rng.random() < 0.7 else rng.choice(pool)
    return item


def case() -> dict:
    blocks = [block(i) for i in range(rng.choice([0, 1, 2, 3]))]
    if len(blocks) > 1 and rng.random() < 0.1:
        blocks[1]["template_id"] = blocks[0]["template_id"]
    if len(blocks) > 1 and rng.random() < 0.1:
        blocks[1].update(days=blocks[0].get("days", [0]), start=blocks[0].get("start", "08:00"))
    item: dict = {"id": "r-1", "name": "School week", "blocks": blocks, "revision": 0}
    if rng.random() < 0.15:
        name, pool = rng.choice([("name", NAMES), ("id", ["", "x" * 81, 5]),
                                 ("revision", [3, -1, "2", 2.0, 2**53, True, None])])  # fmt: skip
        value = rng.choice(pool)
        if value is None and rng.random() < 0.5:
            item.pop(name)
        else:
            item[name] = value
    if rng.random() < 0.03:
        item["extra"] = 1
    return item


def written(item: object) -> dict:
    try:
        return {"input": item, "written": Routine.model_validate(item).model_dump()}
    except Exception:
        return {"input": item, "written": None}


cases = []
seen = set()
while len(cases) < int(sys.argv[2]):
    item = case()
    key = json.dumps(item, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    cases.append(written(item))
with open(sys.argv[1], "w") as out:
    json.dump(cases, out, ensure_ascii=False, separators=(",", ":"))
accepted = sum(1 for c in cases if c["written"] is not None)
print(f"{len(cases)} cases, {accepted} accepted, {len(cases) - accepted} refused")
