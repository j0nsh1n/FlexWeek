"""The split preview parity corpus: generated requests and what `POST /api/timer-split-preview` answers for
each (its preview, or a refusal by `TimerSplitRequest`). Fixed seed, so the corpus is the same on every run.
Run from the repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json> 1200."""

import json
import random
import sys

import flexweek_engine  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator


# The route's request model as it was in backend/app.py (at 19df103f) before the check moved to Rust; kept
# here so the corpus can be made again.
class TimerSplitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_min: int | None = Field(default=None, ge=15, le=7140)
    timer_work_min: int = Field(ge=1, le=180)
    timer_break_min: int = Field(ge=1, le=60)
    timer_long_break_min: int = Field(ge=1, le=120)
    timer_long_break_every: int = Field(ge=2, le=12)

    @field_validator("duration_min")
    @classmethod
    def duration_is_on_the_grid(cls, value: int | None) -> int | None:
        if value is not None and value % 15:
            raise ValueError("duration_min must be a multiple of 15")
        return value


def preview_split(**fields: object) -> dict:
    answer: dict = json.loads(flexweek_engine.preview_split(*fields.values()))
    return answer

rng = random.Random(20261122)
ODD = [None, True, False, "30", " 30 ", "30.0", 30.0, 30.5, "x", "", [], {}, "٣٠", -1, 0, 10**20]
FIELDS = {
    "duration_min": [15, 30, 45, 60, 90, 120, 240, 7140, 7155, 14, 20, 0, 7125, 600, None],
    "timer_work_min": [1, 10, 25, 30, 45, 50, 90, 180, 181, 0, 7],
    "timer_break_min": [1, 5, 10, 15, 60, 61, 0, 7],
    "timer_long_break_min": [1, 15, 20, 30, 120, 121, 0, 7],
    "timer_long_break_every": [2, 3, 4, 12, 13, 1],
}

# Values the model accepts, so most requests reach the split itself.
GOOD = {
    "duration_min": [15, 30, 45, 60, 90, 120, 240, 600, 7125, 7140, None],
    "timer_work_min": [1, 7, 10, 25, 30, 45, 50, 90, 180],
    "timer_break_min": [1, 5, 7, 10, 15, 60],
    "timer_long_break_min": [1, 7, 15, 20, 30, 120],
    "timer_long_break_every": [2, 3, 4, 12],
}


def case() -> object:
    if rng.random() < 0.02:
        return rng.choice([None, [], "x", 3])
    request: dict = {}
    for name, pool in FIELDS.items():
        roll = rng.random()
        if roll < 0.04 and name != "duration_min":
            continue
        if roll < 0.12 and name == "duration_min":
            continue
        if rng.random() < 0.06:
            request[name] = rng.choice(ODD)
        else:
            request[name] = rng.choice(pool) if rng.random() < 0.25 else rng.choice(GOOD[name])
    if rng.random() < 0.02:
        request["extra"] = 1
    return request


def answered(request: object) -> dict:
    try:
        checked = TimerSplitRequest.model_validate(request)
    except Exception:
        return {"input": request, "answer": None}
    return {"input": request, "answer": preview_split(**checked.model_dump())}


cases = []
seen = set()
while len(cases) < int(sys.argv[2]):
    request = case()
    key = json.dumps(request, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    cases.append(answered(request))
with open(sys.argv[1], "w") as out:
    json.dump(cases, out, ensure_ascii=False, separators=(",", ":"))
accepted = sum(1 for c in cases if c["answer"] is not None)
print(f"{len(cases)} cases, {accepted} accepted, {len(cases) - accepted} refused")
