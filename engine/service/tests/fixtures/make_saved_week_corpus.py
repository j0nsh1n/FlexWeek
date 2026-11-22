"""The week save parity corpus: generated week saves and what pydantic's SavedWeek makes of each (the written
save, or a refusal). Fixed seed, so the corpus is the same on every run. Run with the project venv from the
repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 1500."""

import json
import random
import sys

from backend.app import SavedWeek

rng = random.Random(20261122)
WEEK_STARTS = ["2026-11-16", "2026-11-16", "2026-11-17", "2026-13-01", "", "1999-12-27", "2000-01-03",
               "2099-12-28", 20261116, None, "2026-11-16T00:00", "２０２６-11-16"]
REVISIONS = [0, 0, 3, 2**53 - 1, 2**53, -1, "4", 4.0, 4.5, True, None, " 7 "]
STARTS = [None, "09:00", "23:30", "23:45", "24:00", "9:00", "09:60", "٠٩:00", "0٩:30",
          "０９:00", "2٣:00", "", "x"]
BOUNDS = [None, "", "09:00", "Friday 21:00", "friday 21:00", "Fri 21:00", "Friday 25:00", "Sunday 0٩:00",
          "Monday  09:00", "Friday", "21:00 Friday"]
TITLES = ["Guitar", "  ", "　", "\x1f", " ", "Math", "​"]


def block(index: int) -> dict:
    item: dict = {"id": f"b{index}", "title": "Guitar", "kind": rng.choice(["locked", "flexible"])}
    item["duration_min"] = rng.choice([15, 30, 60, 90])
    item["days"] = rng.choice([[0], [2], [1, 3]])
    if item["kind"] == "locked" or rng.random() < 0.4:
        item["start"] = rng.choice(STARTS) if rng.random() < 0.3 else rng.choice(["09:00", "16:30"])
    if rng.random() < 0.1:
        item["title"] = rng.choice(TITLES)
    if rng.random() < 0.08:
        item["days"] = rng.choice([[0, 0], [1, 1, 2]])
    if rng.random() < 0.15:
        item[rng.choice(["earliest", "latest"])] = rng.choice(BOUNDS)
    if rng.random() < 0.05:
        item["duration_min"] = rng.choice([" 30", "45", 60.0, True])
    if rng.random() < 0.06:
        item["pomodoro_parent_id"] = rng.choice(["b0", "b1", "p9"])
    return item


def case() -> dict:
    count = rng.choice([0, 1, 1, 2, 3, 4])
    blocks = [block(i) for i in range(count)]
    if blocks and rng.random() < 0.06:
        blocks[-1]["id"] = blocks[0]["id"]
    if rng.random() < 0.02:
        blocks = [block(i) for i in range(101)]
    save: dict = {"week_start": "2026-11-16", "blocks": blocks, "revision": rng.choice([0, 1, 5])}
    if rng.random() < 0.15:
        save["week_start"] = rng.choice(WEEK_STARTS)
    if rng.random() < 0.12:
        save["revision"] = rng.choice(REVISIONS)
    if rng.random() < 0.04:
        save.pop(rng.choice(["week_start", "blocks", "revision"]))
    if rng.random() < 0.03:
        save["extra"] = 1
    if rng.random() < 0.02:
        save["blocks"] = rng.choice([None, {}, "x"])
    return save


def written(save: object) -> dict:
    try:
        return {"input": save, "written": SavedWeek.model_validate(save).model_dump()}
    except Exception:
        return {"input": save, "written": None}


cases = []
seen = set()
# Fixed cases: the start and deadline patterns read Unicode digits where \d stands, ASCII where a range does.
def one(**fields: object) -> dict:
    base = {"id": "a", "title": "T", "kind": "flexible", "duration_min": 30, "days": [0]}
    return {"week_start": "2026-11-16", "revision": 0, "blocks": [{**base, **fields}]}


for start in ["0\u0669:30", "\u0660\u0669:00", "2\u0663:00", "1\u0669:5\u0669", "\uff10\uff19:00"]:
    cases.append(written(one(kind="locked", start=start)))
for bound in ["Friday 2\u0661:00", "Friday \u0662\u0661:00", "0\u0669:00"]:
    cases.append(written(one(latest=bound)))
for title in TITLES:
    cases.append(written(one(title=title)))
for fixed in cases:
    seen.add(json.dumps(fixed["input"], sort_keys=True))
while len(cases) < int(sys.argv[2]):
    save = case()
    key = json.dumps(save, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    cases.append(written(save))
with open(sys.argv[1], "w") as out:
    json.dump(cases, out, ensure_ascii=False, separators=(",", ":"))
accepted = sum(1 for c in cases if c["written"] is not None)
print(f"{len(cases)} cases, {accepted} accepted, {len(cases) - accepted} refused")
