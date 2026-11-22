"""The backup-file parity corpus: generated account files and what pydantic's TransferSnapshot makes of each
(`model_dump()`, or a refusal). Each starts from a real export of a filled account and changes one or two
things. Fixed seed. Run with the project venv from the repository root, while backend/app.py still holds
TransferSnapshot (it was there at 34e76afb):
PYTHONPATH=. .venv/bin/python <this file> <out.json> 1000."""

from __future__ import annotations

import contextlib
import copy
import json
import random
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import TransferSnapshot, create_app
from backend.tests.account_support import PASSWORD, WRITE

rng = random.Random(20261124)
CASES = json.loads(Path("engine/store/tests/fixtures/repeat_cases.json").read_text())


def exported() -> dict:
    with tempfile.TemporaryDirectory() as folder:
        app = create_app(database=Path(folder) / "t.db", origin="http://testserver")
        with TestClient(app) as c:
            c.post("/api/auth/register", json={"username": "Alice_1", "password": PASSWORD}, headers=WRITE)
            homework = {"id": "hw1", "title": "Essay", "due": "2026-11-20T21:00", "estimate_min": 60}
            session = {"id": "hw1-s1", "title": "Essay", "kind": "flexible", "duration_min": 60, "days": [2],
                       "assignment_id": "hw1", "category": "Homework"}  # fmt: skip
            club = {"id": "club", "title": "Club", "kind": "locked", "duration_min": 60, "days": [3],
                    "start": "16:00", "category": "Club"}  # fmt: skip
            first = {"assignments": [{"id": "hw1", "assignment": homework, "revision": 0}]}
            c.post("/api/changes", json=first, headers=WRITE)
            c.post("/api/changes", json={"weeks": [{"week_start": "2026-11-16", "blocks": [club, session],
                                                    "revision": 0}], "repeats": CASES["setup"]},
                   headers=WRITE)  # fmt: skip
            routine = {"id": "r-1", "name": "School week", "revision": 0, "blocks": [
                {"template_id": "gym", "title": "Gym", "days": [0, 2], "start": "07:00", "duration_min": 45,
                 "category": "Sport"}]}  # fmt: skip
            c.put("/api/routines/r-1", json=routine, headers=WRITE)
            preferences = c.get("/api/preferences").json()
            c.put(
                "/api/preferences",
                json={**preferences, "theme": "nocturne", "clock_24h": True},
                headers=WRITE,
            )
            r = c.post("/api/account-export", json={"password": PASSWORD}, headers=WRITE)
            assert r.status_code == 200, r.text
            return r.json()


BASE = exported()
assert BASE["routines"] and BASE["standing"] and BASE["assignments"] and BASE["weeks"], BASE


def one(item: dict) -> None:
    roll = rng.randrange(24)
    if roll == 0:
        item["format"] = rng.choice([3.0, "3", True, 2, None])
    elif roll == 1:
        item["exported_at"] = rng.choice(
            ["2026-11-22T10:00:30", "2026-11-22", "x", "", 5, "2026-02-30T10:00"]
        )
    elif roll == 2:
        item["username"] = rng.choice(["ALICE", "al", "a" * 32, "a" * 33, "al-ice", "Ålice", "al ice", 5])
    elif roll == 3:
        item[rng.choice(["x", "Format"])] = 1
    elif roll == 4:
        item.pop(rng.choice(["format", "exported_at", "username", "weeks", "assignments", "preferences",
                             "routines", "standing"]))  # fmt: skip
    elif roll == 5:
        item["weeks"].append(copy.deepcopy(item["weeks"][0]))
    elif roll == 6:
        week = item["weeks"][0]
        week[rng.choice(["week_start", "revision"])] = rng.choice(
            ["2026-11-18", "x", -1, "1", 1.0, 2**53, None]
        )
    elif roll == 7:
        item["weeks"][0]["blocks"][0]["assignment_id"] = rng.choice(["hw9", ""])
        item["weeks"][0]["blocks"][0]["kind"] = "flexible"
        item["weeks"][0]["blocks"][0].pop("start", None)
    elif roll == 8:
        item["weeks"][0]["blocks"][0][rng.choice(["duration_min", "days", "extra"])] = rng.choice([7, [9], 1])
    elif roll == 9:
        hw = item["assignments"][0]
        hw[rng.choice(["id", "revision"])] = rng.choice(["hw2", "", -1, "0", 2**53])
    elif roll == 10:
        item["assignments"].append(copy.deepcopy(item["assignments"][0]))
    elif roll == 11:
        item["assignments"][0]["body"][rng.choice(["title", "estimate_min", "x"])] = rng.choice(["", 20, 1])
    elif roll == 12:
        item["preferences"].pop("clock_24h", None)
    elif roll == 13:
        item["preferences"][rng.choice(["theme", "clock_24h", "x", "drag_step_min"])] = rng.choice(
            ["slate", "violet", "yes", 1, 10, None]
        )
    elif roll == 14:
        item["routines"][0].pop(rng.choice(["created_at", "updated_at"]))
    elif roll == 15:
        item["routines"][0][rng.choice(["created_at", "updated_at"])] = rng.choice(["x", "2026-11-22", 5])
    elif roll == 16:
        item["routines"].append(copy.deepcopy(item["routines"][0]))
    elif roll == 17:
        item["routines"][0][rng.choice(["name", "revision", "x"])] = rng.choice(["", " ", -1, 1])
    elif roll == 18:
        item["standing"] = rng.choice([None, [], "x"])
    elif roll == 19:
        row = item["standing"][0]
        row[rng.choice(["position", "from_week", "id"])] = rng.choice(
            [199, 200, -1, "2026-11-18", "", "x" * 81]
        )
    elif roll == 20:
        row = item["standing"][0]
        row["body"] = rng.choice([None, {**(row["body"] or {}), "kind": "flexible"},
                                  {**(row["body"] or {}), "id": "other"}, "x"])  # fmt: skip
    elif roll == 21 and rng.random() < 0.3:
        # Hundreds of rows, now and then: the most standing at once, either side of the cap.
        template = item["standing"][0]
        count = rng.choice([200, 201])
        item["standing"] = [{**copy.deepcopy(template), "id": f"r{i}", "position": i % 200,
                             "body": {**template["body"], "id": f"r{i}"}} for i in range(count)]  # fmt: skip
    elif roll == 22:
        item["standing"][0].pop(rng.choice(["body", "position"]))
    else:
        item["routines"] = [] if rng.random() < 0.5 else item["routines"]
        item["assignments"] = [] if rng.random() < 0.3 else item["assignments"]


def vary(item: dict) -> None:
    """Changes the app accepts, so many files are read in full."""
    week = copy.deepcopy(item["weeks"][0])
    week["week_start"] = rng.choice(["2026-11-23", "2026-11-30", "1999-12-27"])
    week["revision"] = rng.choice([0, 1, 7, 2**53 - 1, 3.0, "4", True])
    item["weeks"].append(week)
    item["assignments"][0]["body"]["title"] = rng.choice(["Lab", "Été", "日本", " x "])
    item["assignments"][0]["revision"] = rng.choice([0, 5, "2"])
    item["preferences"]["theme"] = rng.choice(["system", "slate", "nocturne"])
    item["preferences"]["clock_24h"] = rng.choice([True, False, "yes", 0])
    item["routines"][0]["name"] = rng.choice(["Week", "Été"])
    item["routines"][0]["updated_at"] = rng.choice(["2026-11-22T10:00", "2026-01-01T00:00"])
    item["standing"][0]["position"] = rng.choice([0, 1, 199, "3"])
    item["username"] = rng.choice(["Alice_1", "BOB", "c_d"])


def case() -> object:
    if rng.random() < 0.01:
        return rng.choice([None, [], "x"])
    item = copy.deepcopy(BASE)
    if rng.random() < 0.6:
        vary(item)
    for _ in range(rng.choice([0, 0, 1, 1, 2])):
        with contextlib.suppress(KeyError, IndexError, TypeError, AttributeError):
            one(item)
    return item


def written(item: object) -> dict:
    try:
        return {"input": item, "written": TransferSnapshot.model_validate(item).model_dump()}
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
