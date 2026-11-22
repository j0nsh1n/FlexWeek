"""The homework save parity corpus: generated homework saves and what pydantic's Assignment makes of each (the
written homework, or a refusal). Fixed seed, so the corpus is the same on every run. Run with the project venv
from the repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 2000."""

import json
import random
import sys

from backend.models import Assignment

rng = random.Random(20261122)
TITLES = ["Essay", "  ", "　", "x" * 80, "x" * 81, "", 5, None, "Été", "\x1f"]
DUES = ["2026-11-20T21:00", "2026-11-20", "2026-11-20T21:00:30", "2026-02-30", "tomorrow", "", None,
        "2026-11-20 21:00", "２０２６-11-20", "1999-12-31", "2100-01-01T00:00"]
ESTIMATES = [15, 30, 60, 120, 0, -15, 20, 7140, 7155, " 60", "60.0", 60.0, 60.5, True, None, "x"]
INTS = [0, 3, 9999, 10000, 71400, 71401, -1, "3", 3.0, 3.5, True, None]
BOOLS = [True, False, "yes", "no", 0, 1, "maybe", None, 2]
STAMPS = [None, "2026-11-20T21:00", "2026-11-20T21:00:30", "2026-11-20", "x", ""]
LINKS = [[], [{"label": "Doc", "url": "https://example.com/a"}], [{"label": " ", "url": "https://x.org"}],
         [{"label": "Doc", "url": "ftp://x.org"}], [{"label": "Doc", "url": "https://user@x.org"}],
         [{"label": "Doc"}], [{"label": "Doc", "url": "https://x.org", "extra": 1}], "x", None]
CHECKLISTS = [[], [{"id": "c1", "text": "Read", "done": True}], [{"id": "c1", "text": "Read"}],
              [{"id": "c1", "text": "A"}, {"id": "c1", "text": "B"}], [{"id": "c1", "text": "  "}],
              [{"id": "c1", "text": "Read", "done": "yes"}], [{"id": "", "text": "Read"}], None]
OPTIONAL = {
    "course": [None, "Chem", "", "x" * 40, "x" * 41, 3], "category": [None, "Homework", "x" * 33],
    "priority": [1, 4, 0, 5, 2.0, True, "2", None], "energy": ["high", "low", "HIGH", None],
    "spotify_url": [None, "", "https://open.spotify.com/track/abc", "http://open.spotify.com/track/a"],
    "spread": ["one", "spread", "two", None], "focus_minutes": INTS, "focus_sessions": INTS,
    "notes": ["", "Outline", "x" * 4000, "x" * 4001, None], "links": LINKS, "checklist": CHECKLISTS,
    "unknown": [1],
}

# Values the model accepts, so most saves reach how the homework is written.
GOOD = {
    "course": [None, "Chem", ""], "category": [None, "Homework"], "priority": [1, 4, 2.0, True],
    "energy": ["high", "low"], "spotify_url": [None, "", "https://open.spotify.com/track/abc"],
    "spread": ["one", "spread"], "focus_minutes": [0, 3, "3", 3.0, 71400], "focus_sessions": [0, 3, True],
    "notes": ["", "Outline", "x" * 4000], "links": LINKS[:2], "checklist": CHECKLISTS[:3] + [CHECKLISTS[5]],
    "unknown": [1],
}


def case() -> dict:
    item: dict = {"id": "hw1", "title": "Essay", "due": "2026-11-20T21:00", "estimate_min": 60, "revision": 0}
    if rng.random() < 0.25:
        required = [("title", TITLES), ("due", DUES), ("estimate_min", ESTIMATES + [1440, 1455]),
                    ("id", ["", "x" * 81, 7, None]), ("revision", [*INTS, 2**53, " 2 "])]
        name, pool = rng.choice(required)
        value = rng.choice(pool)
        if value is None and rng.random() < 0.5:
            item.pop(name)
        else:
            item[name] = value
    for name, pool in OPTIONAL.items():
        if rng.random() < 0.12:
            item[name] = rng.choice(GOOD[name]) if rng.random() < 0.7 else rng.choice(pool)
    if rng.random() < 0.25:
        item["completed"] = rng.choice(BOOLS)
        if rng.random() < 0.8:
            done = item["completed"] in (True, "yes", 1)
            item["completed_at"] = "2026-11-20T21:00" if done and rng.random() < 0.6 else rng.choice(STAMPS)
    return item


def written(item: object) -> dict:
    try:
        return {"input": item, "written": Assignment.model_validate(item).model_dump()}
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
