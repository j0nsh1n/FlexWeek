"""The Plan request parity corpus: generated Plan requests and what pydantic's SolveRequest makes of each (the
request as read, or a refusal). Fixed seed. Run with the project venv from the repository root:
PYTHONPATH=. .venv/bin/python <this file> <out.json> 1500."""

import json
import random
import sys

from backend.models import SolveRequest

rng = random.Random(20261122)
WEEK_STARTS = [None, "2026-11-16", "2026-11-18", "2026-11-16T00:00", "1999-12-27", "x", 5, ""]
FLOORS = [None, [2, 600], [0, 0], (6, 1439), [2], [2, 600, 1], ["2", "600"], [2.0, 600.0], [2.5, 600], "x", 5]
MINUTES = [15, 30, 60, 45, "30", 30.0, True, None]
STARTS = ["16:00", "16:10", "24:00", "0٩:00", "9:00", "", None]


def block(index: int, **more: object) -> dict:
    item: dict = {"id": f"b{index}", "title": "Work", "kind": rng.choice(["locked", "flexible"]),
                  "duration_min": rng.choice([30, 60]), "days": [index % 5]}  # fmt: skip
    if item["kind"] == "locked":
        item["start"] = f"{8 + index:02d}:00"
    if rng.random() < 0.1:
        item["assignment_id"] = "hw1"
        item["kind"] = "flexible"
    return {**item, **more}


def case() -> object:
    if rng.random() < 0.02:
        return rng.choice([None, [], "x"])
    blocks = [block(i) for i in range(rng.choice([0, 1, 2, 3]))]
    item: dict = {"blocks": blocks}
    if rng.random() < 0.5:
        item["week_start"] = rng.choice(WEEK_STARTS) if rng.random() < 0.4 else "2026-11-16"
    if rng.random() < 0.2:
        item["now_floor"] = rng.choice(FLOORS)
    mode = rng.random()
    if mode < 0.2:
        target = blocks[0]["id"] if blocks and rng.random() < 0.7 else "nope"
        day = blocks[0]["days"][0] if blocks and rng.random() < 0.7 else rng.choice([6, 7, -1, "1"])
        item["recover"] = {"missed_block_id": target, "missed_day": day,
                           "previous_placed": [block(9)] if rng.random() < 0.5 else []}  # fmt: skip
        if rng.random() < 0.1:
            item["recover"]["extra"] = 1
        if rng.random() < 0.1:
            item["recover"]["previous_placed"] = [block(9), block(9)]
    elif mode < 0.4:
        item["running_late"] = {"day": rng.choice([0, 3, 6, 7, "2"]), "minutes": rng.choice(MINUTES),
                                "from_start": rng.choice(STARTS) if rng.random() < 0.4 else "16:00",
                                "previous_placed": []}  # fmt: skip
        if rng.random() < 0.2:
            item["running_late"]["now_floor"] = rng.choice(FLOORS)
        if rng.random() < 0.1:
            item["running_late"]["extra"] = 1
    elif mode < 0.45:
        item["recover"] = {"missed_block_id": "b0", "missed_day": 0, "previous_placed": []}
        item["running_late"] = {"day": 0, "minutes": 30, "from_start": "16:00", "previous_placed": []}
    if rng.random() < 0.05:
        item["unknown"] = 1
    if blocks and rng.random() < 0.3:
        shaped(item, blocks)
    return item


def shaped(item: dict, blocks: list[dict]) -> None:
    """One of WeekRequest's block-list rules, or a missed day, on an otherwise ordinary request."""
    first = blocks[0]
    rule = rng.choice(["missed", "missed", "duplicate", "no-start", "bound", "pomodoro", "too-many"])
    if rule == "missed":
        # A missed day already marked, a day the block is not on, or a missed day on a flexible block.
        first["missed_days"] = rng.choice([[first["days"][0]], [6], [first["days"][0], first["days"][0]], []])
        if rng.random() < 0.5 and first["kind"] == "locked":
            item.pop("running_late", None)
            item["recover"] = {"missed_block_id": first["id"], "missed_day": first["days"][0],
                               "previous_placed": []}  # fmt: skip
    elif rule == "duplicate":
        blocks.append(dict(first))
    elif rule == "no-start":
        first["kind"] = "locked"
        first.pop("start", None)
        first.pop("assignment_id", None)
    elif rule == "bound":
        bound = rng.choice(["Monday 09:00", "09:00", "Funday 09:00", "24:00", "", "monday 09:00"])
        first[rng.choice(["earliest", "latest"])] = bound
    elif rule == "pomodoro":
        blocks.append(block(len(blocks), kind="flexible", pomodoro_parent_id=first["id"]))
    else:
        # Valid placements on either side of the cap of 100, against a missed block that exists.
        previous = [{"id": f"p{i}", "title": "Work", "kind": "flexible", "duration_min": 30, "days": [i % 5]}
                    for i in range(rng.choice([100, 101]))]  # fmt: skip
        first.update(kind="locked", start="08:00")
        first.pop("assignment_id", None)
        item.pop("running_late", None)
        item["recover"] = {"missed_block_id": first["id"], "missed_day": first["days"][0],
                           "previous_placed": previous}  # fmt: skip


def written(item: object) -> dict:
    try:
        return {"input": item, "written": SolveRequest.model_validate(item).model_dump(mode="json")}
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
