"""The multi-week save parity corpus: generated `POST /api/changes` bodies, what pydantic's ChangesRequest
makes of each (`model_dump()`, or a refusal), and the digest that keys a remembered answer. ChangesRequest
left backend/app.py when the route moved to Rust; its models are copied here as they were at 23720ad1.
Fixed seed. Run with the project venv from the repository root:
PYTHONPATH=. .venv/bin/python <this file> <out.json> 2500."""

from __future__ import annotations

import json
import random
import sys
from typing import Annotated

import flexweek_engine
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.models import AssignmentContent, WeekRequest
from backend.weeks import is_calendar_date, is_week_start

SHOWN_WEEK_RULE = (
    "week_start must be a date from 2000-01-01 through 2099-12-31. A Monday names its revision; "
    "a week from another day names the revisions of the two stored weeks it covers"
)
Revision = Annotated[int, Field(ge=0, le=2**53 - 1)]
MAX_REPEAT_CHANGES = 2 * int(flexweek_engine.MAX_REPEATS)


class ChangedWeek(WeekRequest):
    model_config = ConfigDict(extra="forbid")
    week_start: str
    revision: Revision | list[Revision]

    @model_validator(mode="after")
    def revision_fits_the_week(self) -> ChangedWeek:
        if is_week_start(self.week_start):
            if not isinstance(self.revision, int):
                raise ValueError(SHOWN_WEEK_RULE)
        elif not (is_calendar_date(self.week_start) and isinstance(self.revision, list)):
            raise ValueError(SHOWN_WEEK_RULE)
        if isinstance(self.revision, list) and len(self.revision) != 2:
            raise ValueError(SHOWN_WEEK_RULE)
        return self


class AssignmentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    assignment: AssignmentContent | None
    revision: int = Field(ge=0, le=2**53 - 1)


class ChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weeks: list[ChangedWeek] = Field(default_factory=list)
    assignments: list[AssignmentChange] = Field(default_factory=list)
    operation_id: str | None = Field(default=None, min_length=1, max_length=80)
    snapshot_label: str | None = Field(default=None, min_length=1, max_length=80)
    repeats: list[dict] | None = Field(default=None, max_length=MAX_REPEAT_CHANGES)


rng = random.Random(20261123)
MONDAYS = ["2026-11-16", "2026-11-23", "1999-12-27", "2000-01-03"]
OTHER_DAYS = ["2026-11-18", "2026-11-22", "2026-02-29", "2026-11-18T00:00", "2026-13-01", "x", "", 5, None]
REVISIONS = [0, 3, 2**53 - 1, 2**53, -1, "3", 3.0, 3.5, True, None, "x"]
TEXTS = ["op-1", " ", "", "x" * 80, "x" * 81, "Été", 5, None, ["op"]]


def block(index: int) -> dict:
    item: dict = {"id": f"b{index}", "title": "Work", "kind": rng.choice(["locked", "flexible"]),
                  "duration_min": rng.choice([30, 60]), "days": [index % 5]}  # fmt: skip
    if item["kind"] == "locked":
        item["start"] = f"{8 + index:02d}:00"
    if rng.random() < 0.05:
        item["duration_min"] = rng.choice([0, 7, "60", 60.0])
    if rng.random() < 0.05:
        item["id"] = "b0"
    return item


def revision() -> object:
    return rng.choice(REVISIONS) if rng.random() < 0.3 else rng.choice([0, 1, 7])


def week() -> object:
    if rng.random() < 0.02:
        return rng.choice([None, [], "x"])
    shown = rng.random() < 0.4
    start = rng.choice(OTHER_DAYS if shown else MONDAYS) if rng.random() < 0.3 else (
        "2026-11-18" if shown else "2026-11-16")  # fmt: skip
    item: dict = {"week_start": start, "blocks": [block(i) for i in range(rng.choice([0, 1, 2, 3]))]}
    roll = rng.random()
    if roll < 0.15:
        item["revision"] = revision()
    elif roll < 0.25:
        item["revision"] = rng.choice([[1], [1, 2, 3], [], [revision(), revision()], "x"])
    else:
        item["revision"] = [revision(), revision()] if shown else revision()
    if rng.random() < 0.05:
        item.pop(rng.choice(["week_start", "blocks", "revision"]))
    if rng.random() < 0.03:
        item["extra"] = 1
    return item


def homework(hw_id: str) -> object:
    body: dict = {"id": hw_id, "title": rng.choice(["Essay", "Essay", "  ", ""]), "due": "2026-11-20T21:00",
                  "estimate_min": rng.choice([60, 60, 20, "60"])}  # fmt: skip
    if rng.random() < 0.2:
        body["notes"] = rng.choice(["Outline", None, "x" * 4001])
    if rng.random() < 0.2:
        body["priority"] = rng.choice([1, 4, 0, True])
    if rng.random() < 0.05:
        body["revision"] = 1
    return body


def change() -> object:
    if rng.random() < 0.02:
        return rng.choice([None, "x", []])
    hw_id = rng.choice(["hw1", "hw2", "", "x" * 81, 5]) if rng.random() < 0.1 else "hw1"
    item: dict = {"id": hw_id, "revision": revision()}
    roll = rng.random()
    if roll < 0.4:
        item["assignment"] = None
    elif roll < 0.95:
        item["assignment"] = homework(rng.choice(["hw1", "hw2"]) if rng.random() < 0.2 else str(hw_id))
    if rng.random() < 0.03:
        item["extra"] = 1
    return item


def repeat() -> object:
    if rng.random() < 0.05:
        return rng.choice([1, "x", None, []])
    item: dict = {"action": rng.choice(["add", "stop", "edit"]), "from_week": "2026-11-16", "id": "school"}
    if rng.random() < 0.3:
        item["number"] = rng.choice([1.0, 1e5, 2.5, -0.0, 10**20])
    return item


def case() -> object:
    if rng.random() < 0.02:
        return rng.choice([None, [], "x", 5])
    item: dict = {}
    if rng.random() < 0.7:
        item["weeks"] = [week() for _ in range(rng.choice([0, 1, 1, 2, 3]))]
    if rng.random() < 0.5:
        item["assignments"] = [change() for _ in range(rng.choice([0, 1, 2]))]
    for name in ("operation_id", "snapshot_label"):
        if rng.random() < 0.4:
            item[name] = rng.choice(TEXTS) if rng.random() < 0.4 else f"{name}-1"
    if rng.random() < 0.3:
        # The cap on either side, now and then: each such list holds hundreds of changes.
        count = rng.choice([0, 1, 2, 3]) if rng.random() < 0.97 else rng.choice([MAX_REPEAT_CHANGES,
                                                                                 MAX_REPEAT_CHANGES + 1])
        listed = [repeat() for _ in range(count)] if count < 4 else [
            {"action": "stop", "from_week": "2026-11-16", "id": f"r{i}"} for i in range(count)]
        item["repeats"] = listed if rng.random() < 0.9 else rng.choice([None, "x", {}])
    for name in ("weeks", "assignments"):
        if rng.random() < 0.02:
            item[name] = rng.choice([None, "x", {}])
    if rng.random() < 0.03:
        item["unknown"] = 1
    return item


def written(item: object) -> dict:
    try:
        dumped = ChangesRequest.model_validate(item).model_dump()
    except Exception:
        return {"input": item, "written": None, "digest": None}
    return {"input": item, "written": dumped, "digest": flexweek_engine.payload_digest(dumped)}


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
