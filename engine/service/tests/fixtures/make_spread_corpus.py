"""The spread request parity corpus: generated "spread it out" requests and what pydantic's SpreadRequest
makes of each (the request as read, or a refusal). Fixed seed. Run with the project venv from the
repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 800."""

import json
import random
import sys

from backend.models import SpreadRequest

rng = random.Random(20261122)
MINUTES = [15, 30, 45, 60, 90, 180, 195, 0, 10, 20, " 30", "30.0", 30.0, 30.5, True, None, "x", 10**20]
DATES = ["2026-11-20", "2000-01-01", "2099-12-31", "1999-12-31", "2100-01-01", "2026-02-30", "2026-1-1",
         "２０２６-11-20", "٢٠٢٦-١١-٢٠", "2026-11-20T00:00",
         "20261120", "", None, 20261120, " 2026-11-20"]


def case() -> object:
    if rng.random() < 0.03:
        return rng.choice([None, [], "x"])
    item: dict = {"session_min": rng.choice(MINUTES) if rng.random() < 0.6 else rng.choice([30, 60]),
                  "from_date": rng.choice(DATES) if rng.random() < 0.6 else "2026-11-20"}  # fmt: skip
    if rng.random() < 0.05:
        item.pop(rng.choice(["session_min", "from_date"]))
    if rng.random() < 0.03:
        item["extra"] = 1
    return item


def written(item: object) -> dict:
    try:
        return {"input": item, "written": SpreadRequest.model_validate(item).model_dump()}
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
