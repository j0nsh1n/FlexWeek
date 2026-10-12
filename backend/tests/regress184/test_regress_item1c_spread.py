"""Regression for fix-specs.md item 1c: Plan crams homework into today and never uses the weekend.

Inputs are Timmy's 18 test weeks (/workspace/fw184/solver-compare/harness/weeks.json, copied to
backend/tests/data/regress_1c_weeks.json; day 0 = Monday). The engine's solver is called as
backend/solver.py calls it, but with a fixed-work clock in place of the wall clock: each clock read
advances it by PER_CHECK_MS, so the 150 ms budget is the same amount of search on every machine and the
plans are deterministic. 0.001 ms per check matches the app's 150 ms on the box the comparison ran on
(the placed counts equal report.md's "Today" column); 0.004 is Timmy's "4x slower laptop".

Guards (spec 1c): week 17 uses Sat/Sun with Friday at most the cap; week 2 has no day over the cap while
a lighter day before the due date has room, and nothing ends later than 1 day before its due date when
room exists; no week places fewer items than today's planner; a priority-1 item is never dropped for a
lower one; no homework starts within 30 min of School's end. Part A (session_days) is also pinned in
engine/engine/tests/test_regress_item1c_session_days.rs. Known failures are xfail(strict=True).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

WEEKS = json.loads((Path(__file__).parent.parent / "data" / "regress_1c_weeks.json").read_text())
BY_NAME = {week["name"].split(".")[0]: week for week in WEEKS}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CAP_MIN = 150  # spec 1c.B default "Most homework per day"
AFTER_SCHOOL_GAP = 30
# Items today's planner places in each week (report.md "Today"), at 1x and at 4x slower.
TODAY = {"1": 3, "2": 8, "3": 22, "4": 60, "5": 8, "6": 10, "7": 6, "8": 6, "9": 9, "10": 6, "11": 25,
         "12": 27, "13": 30, "14": 22, "15": 15, "16": 40, "17": 3, "17b": 3}
TODAY_SLOW = {**TODAY, "10": 5, "15": 14}
KNOWN_WEEKEND = (
    "known failure (item 1c.A): due after Sunday offers Mon-Fri only, so a Friday plan puts all 3 h 15 min "
    "on Friday and nothing on the weekend"
)
KNOWN_SPREAD = "known failure (item 1c.B): the solver fills the earliest slot; 7 h of homework on Monday"
KNOWN_GAP = "known failure (item 1c.B): homework starts at School's end (15:15), no 30 min gap"


def hm(text: str) -> int:
    hours, minutes = map(int, text.split(":"))
    return hours * 60 + minutes


def solve(week: dict, per_check_ms: float = 0.001) -> dict:
    checks = [0]

    def clock() -> float:
        checks[0] += 1
        return checks[0] * per_check_ms

    raw = flexweek_engine.solve(
        json.dumps(week["blocks"]),
        json.dumps(week["deadlines"]) if week.get("deadlines") else None,
        json.dumps(week["slack"]) if week.get("slack") else None,
        [int(x) for x in week["extra_occ"]] if week.get("extra_occ") else None,
        json.dumps(week["work_windows"]) if week.get("work_windows") else None,
        clock,
    )
    return json.loads(raw)


def homework(week: dict) -> dict[str, dict]:
    return {b["id"]: b for b in week["blocks"] if b["kind"] == "flexible" and not b.get("pinned")}


def placed(week: dict, trace: dict) -> dict[str, tuple[int, int, int]]:
    """id -> (day, start, end) for the homework the plan gave a time."""
    items = homework(week)
    out = {}
    for block in trace["placed"]:
        if block["id"] in items and block.get("start"):
            start = hm(block["start"])
            out[block["id"]] = (block["days"][0], start, start + items[block["id"]]["duration_min"])
    return out


def due_point(week: dict, block: dict) -> tuple[int, int]:
    """(day, minute) of the due time; a day past Sunday for work due next week."""
    if week.get("slack") and block["id"] in week["slack"]:
        day, minute = week["slack"][block["id"]]
        return int(day), int(minute)
    day, at = block["latest"].split()
    return DAYS.index(day), hm(at)


def per_day(times: dict[str, tuple[int, int, int]]) -> Counter:
    load: Counter = Counter()
    for day, start, end in times.values():
        load[day] += end - start
    return load


# A. Week 17 -------------------------------------------------------------------------------------


def week17_as_the_app_asks() -> dict:
    """Week 17 with each item's days rebuilt the way the app builds them: session_days for its due date
    (the engine's own function), then only today and later (Friday 10:45)."""
    week = json.loads(json.dumps(BY_NAME["17"]))
    due = {"n1": "2026-10-14T23:59", "n2": "2026-10-15T23:59", "n3": "2026-10-16T23:59"}
    now_day = 4
    for block in week["blocks"]:
        if block["id"] in due:
            offered = list(flexweek_engine.reuse_session_days("2026-10-05", json.dumps(due[block["id"]])))
            block["days"] = [day for day in offered if day >= now_day]
    return week


def test_week17_offers_plan_friday_at_least() -> None:
    """Guard: the request is built and solved; all three items get a time this week."""
    week = week17_as_the_app_asks()
    assert len(placed(week, solve(week))) == 3


@pytest.mark.xfail(strict=True, reason=KNOWN_WEEKEND)
def test_week17_uses_the_weekend_and_friday_stays_under_the_cap() -> None:
    week = week17_as_the_app_asks()
    times = placed(week, solve(week))
    load = per_day(times)
    assert load[5] + load[6] > 0, f"nothing on Sat/Sun: {times}"
    assert load[4] <= CAP_MIN, f"Friday has {load[4]} min"


# B. Week 2 --------------------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=KNOWN_SPREAD)
def test_week2_no_day_over_the_cap_while_a_lighter_day_before_the_due_date_has_room() -> None:
    week = BY_NAME["2"]
    items = homework(week)
    times = placed(week, solve(week))
    load = per_day(times)
    crammed = []
    for item_id, (day, start, end) in times.items():
        if load[day] <= CAP_MIN:
            continue
        due_day, _due_min = due_point(week, items[item_id])
        room = [d for d in items[item_id]["days"] if d < due_day and d != day and load[d] + end - start <= CAP_MIN]
        if room:
            crammed.append((items[item_id]["title"], DAYS[day], load[day], [DAYS[d] for d in room]))
    assert crammed == [], f"per day {dict(load)}"


@pytest.mark.xfail(strict=True, reason=KNOWN_SPREAD)
def test_week2_nothing_ends_later_than_a_day_before_its_due_date_when_room_exists() -> None:
    week = BY_NAME["2"]
    items = homework(week)
    now_day, now_min = week["now"][0], hm(week["now"][1])
    late = []
    for item_id, (day, _start, end) in placed(week, solve(week)).items():
        due_day, due_min = due_point(week, items[item_id])
        lead = (due_day - now_day) * 1440 + due_min - now_min
        if lead < 2 * 1440:  # due within two days of now: no room for a day's buffer is expected
            continue
        slack = (due_day - day) * 1440 + due_min - end
        if slack < 1440:
            late.append((items[item_id]["title"], DAYS[day], slack))
    assert late == []
    # As a check that the rule is not vacuous: today the History essay (due Thu) is done Monday.
    assert any(due_point(week, b)[0] >= 3 for b in items.values())


@pytest.mark.xfail(strict=True, reason=KNOWN_GAP)
def test_no_homework_starts_within_30_minutes_of_school_ending() -> None:
    week = BY_NAME["2"]
    school = next(b for b in week["blocks"] if b["id"] == "school")
    ends = hm(school["start"]) + school["duration_min"]
    too_soon = [
        (item_id, DAYS[day], start)
        for item_id, (day, start, _end) in placed(week, solve(week)).items()
        if day in school["days"] and ends <= start < ends + AFTER_SCHOOL_GAP
    ]
    assert too_soon == []


# No week places fewer items than today; priority 1 is never dropped for a lower one ------------


@pytest.mark.parametrize(("per_check_ms", "floor"), [(0.001, TODAY), (0.004, TODAY_SLOW)], ids=["1x", "4x-slower"])
@pytest.mark.parametrize("name", list(BY_NAME))
def test_no_week_places_fewer_items_than_today(name: str, per_check_ms: float, floor: dict) -> None:
    week = BY_NAME[name]
    count = len(placed(week, solve(week, per_check_ms)))
    assert count >= floor[name], f"{week['name']}: {count} placed, today {floor[name]}"


@pytest.mark.parametrize("per_check_ms", [0.001, 0.004], ids=["1x", "4x-slower"])
@pytest.mark.parametrize("name", list(BY_NAME))
def test_a_priority_1_item_is_never_dropped_for_a_lower_one(name: str, per_check_ms: float) -> None:
    week = BY_NAME[name]
    items = homework(week)
    got = placed(week, solve(week, per_check_ms))
    dropped = [i for i, b in items.items() if b.get("priority") == 1 and i not in got]
    lower = [i for i in got if (items[i].get("priority") or 3) > 1]
    assert not (dropped and lower), f"{week['name']}: priority 1 {dropped} dropped, {len(lower)} lower placed"
