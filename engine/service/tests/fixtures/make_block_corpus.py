"""The block parity corpus: generated blocks and what pydantic's TimeBlock makes of each (the written
block, or a refusal). Fixed seed, so the corpus is the same on every run. Run with the project venv
from the repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 2500."""

import json
import random
import sys

from backend.models import TimeBlock

rng = random.Random(20261122)
ID = ["a", "blk-1", "x" * 80, "x" * 81, "", 5, None, "é" * 80]
TITLE = ["Guitar", "T", "  ", "x" * 80, "x" * 81, "", 7, None, "日本語"]
KIND = ["locked", "flexible", "Locked", "", None, 1]
INTS = [
    0, 1, 30, 7140, 7141, -1, 30.0, 30.5, True, False, "30", " 30 ", "+30", "030", "30.0", "30.00",
    "1_0", "1__0", "_10", "3e1", "", "abc", None, 10**20, 1e30, "٣٠", "-0", [30],
]
DAYS = [
    [0], [0, 1, 2, 3, 4, 5, 6], [], [0] * 8, [7], [-1], [0, 0],
    ["1"], [True], [1.0], [1.5], "0", None, [None],
]
PRIORITY = [1, 2, 3, 4, 0, 5, 2.0, 2.5, True, False, "2", None]
ENERGY = ["high", "medium", "low", "HIGH", "", None, 3]
OPT_TEXT = [None, "", "09:00", "x" * 5, "x" * 6, "x" * 40, "x" * 41, 9]
BOOLS = [True, False, 0, 1, 2, -1, 0.0, 1.0, 0.5, "yes", "No", "on", "OFF", "t", "F", "y", "n", "1", "0",
         "true", "TRUE", "  true  ", "2", "", None]
SMALL = [None, 0, 3, 6, 7, -1, "3", 3.0, True]
MISSED = [[], [0], [0, 0], [6], [7], None, [1, 2]]
SPOTIFY = [None, "", "https://open.spotify.com/track/abc123", "https://open.spotify.com/track/abc123?si=x",
           "http://open.spotify.com/track/abc", "https://open.spotify.com/artist/abc",
           "https://user@open.spotify.com/track/abc", "https://open.spotify.com:443/track/abc", 5]
ROLE = [None, "work", "break", "rest", ""]
UNTIL = [None, "2026-12-31", "2026-02-30", "2026-1-1", "", "1999-12-31", "2100-01-01", 20261231]

OPTIONAL = {
    "priority": PRIORITY, "energy": ENERGY, "earliest": OPT_TEXT, "latest": OPT_TEXT, "start": OPT_TEXT,
    "course": OPT_TEXT, "category": OPT_TEXT + ["x" * 32, "x" * 33], "completed": BOOLS,
    "completed_day": SMALL, "missed_days": MISSED, "spotify_url": SPOTIFY, "focus_sessions": INTS,
    "focus_minutes": INTS, "pomodoro_parent_id": ID, "pomodoro_role": ROLE, "pomodoro_index": INTS,
    "pinned": BOOLS, "prefer_earliest": BOOLS, "keep_whole": BOOLS, "assignment_id": ID, "until": UNTIL,
    "unknown_extra": [1, "x"],
}


GOOD = {
    "priority": [1, 2, 3, 4, 2.0, True], "energy": ["high", "medium", "low"], "earliest": [None, "", "09:00"],
    "latest": [None, "17:00"], "start": [None, "16:00", "9"], "course": [None, "Math"],
    "category": [None, "class", "x" * 32],
    "completed": [True, False, "yes", 0, 1.0], "completed_day": [None], "missed_days": [[], None],
    "spotify_url": [None, "", "https://open.spotify.com/track/abc123"], "focus_sessions": [0, 2, "3", 9999],
    "focus_minutes": [0, 25, 71400], "pomodoro_parent_id": [None, "p1"], "pomodoro_role": [None, "break"],
    "pomodoro_index": [None, 1, 999], "pinned": [False, "no"], "prefer_earliest": [True, False],
    "keep_whole": [True, "off"], "assignment_id": [None], "until": [None, "2026-12-31"], "unknown_extra": [1],
}


def valid_base() -> dict:
    return {"id": "a", "title": "Guitar", "kind": rng.choice(["locked", "flexible"]),
            "duration_min": rng.choice([15, 30, 60]), "days": rng.choice([[0], [2], [1, 3], [4]])}


def case() -> dict:
    block = valid_base()
    mode = rng.random()
    if mode < 0.2:  # one required field varied
        required = [("id", ID), ("title", TITLE), ("kind", KIND), ("duration_min", INTS), ("days", DAYS)]
        name, pool = rng.choice(required)
        value = rng.choice(pool)
        if value is None and rng.random() < 0.5:
            block.pop(name)
        else:
            block[name] = value
    for name, pool in OPTIONAL.items():  # some optional fields, mostly few at a time
        if rng.random() < (0.06 if mode < 0.7 else 0.2):
            # Half the time a value pydantic accepts for that field, to reach the writing rules.
            block[name] = rng.choice(GOOD.get(name, pool)) if rng.random() < 0.6 else rng.choice(pool)
    if rng.random() < 0.15:  # a session or a pinned/completed shape, the cross-field rules
        block.update(kind="flexible", start="16:00", days=[rng.choice([0, 3])])
        block[rng.choice(["pinned", "completed", "assignment_id"])] = rng.choice([True, "h1"])
        if rng.random() < 0.5:
            block["completed"] = True
            block["completed_day"] = block["days"][0] if rng.random() < 0.7 else 5
    return block


cases = []
seen = set()
while len(cases) < int(sys.argv[2]):
    block = case()
    key = json.dumps(block, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    try:
        cases.append({"input": block, "written": TimeBlock.model_validate(block).model_dump()})
    except Exception:
        cases.append({"input": block, "written": None})
with open(sys.argv[1], "w") as out:
    json.dump(cases, out, ensure_ascii=False, separators=(",", ":"))
accepted = sum(1 for c in cases if c["written"] is not None)
print(f"{len(cases)} cases, {accepted} accepted, {len(cases) - accepted} refused")
