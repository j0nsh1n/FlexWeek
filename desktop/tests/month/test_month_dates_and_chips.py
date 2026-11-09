# ruff: noqa: F811
"""The Material month's dates and the words on each chip, as the bridge hands them to the screen."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from desktop.native.material.bridge_month import read_cells  # noqa: E402
from desktop.tests.month.support_month_bridge import (  # noqa: E402, F401
    FakeSession,
    chips,
    deadlines,
    isos,
    snapshot,
    week_start,
)


@pytest.mark.parametrize(
    ("month", "start", "first", "last", "count"),
    [
        # 1 November 2026 is a Sunday and 30 November a Monday: six rows from Monday, five from Sunday.
        ("2026-11", "monday", "2026-10-26", "2026-12-06", 42),
        ("2026-11", "sunday", "2026-11-01", "2026-12-05", 35),
        # December crosses into the next year: 1 Dec is a Tuesday, 31 Dec a Thursday.
        ("2026-12", "monday", "2026-11-30", "2027-01-03", 35),
        ("2026-12", "sunday", "2026-11-29", "2027-01-02", 35),
        # February 2027 starts on a Monday and ends on a Sunday: exactly four rows from Monday.
        ("2027-02", "monday", "2027-02-01", "2027-02-28", 28),
        ("2027-02", "sunday", "2027-01-31", "2027-03-06", 35),
    ],
)
def test_the_grid_runs_from_the_week_start_across_month_edges(
    week_start, month: str, start: str, first: str, last: str, count: int
) -> None:
    week_start(start)
    rows, names = read_cells(FakeSession(month, snapshot(month)))
    assert len(rows) == count
    assert (rows[0]["iso"], rows[-1]["iso"]) == (first, last)
    assert len(set(isos(rows))) == count
    assert names[0] == ("Sun" if start == "sunday" else "Mon")
    assert len(names) == 7
    inside = [row["iso"] for row in rows if row["inMonth"]]
    assert inside[0] == f"{month}-01"
    assert all(iso.startswith(month) for iso in inside)
    assert len(inside) == {"2026-11": 30, "2026-12": 31, "2027-02": 28}[month]


def test_the_grid_is_empty_until_a_month_is_open(week_start) -> None:
    session = FakeSession("2026-11", None)
    session.selected_month = None
    assert read_cells(session)[0] == []
    session.account = None
    assert read_cells(session)[0] == []


def test_today_and_the_quiet_days_are_marked(week_start) -> None:
    rows, _ = read_cells(FakeSession("2026-11", snapshot("2026-11")))
    by_iso = {row["iso"]: row for row in rows}
    assert [iso for iso, row in by_iso.items() if row["today"]] == ["2026-11-02"]
    assert by_iso["2026-10-31"]["inMonth"] is False
    assert by_iso["2026-11-01"]["inMonth"] is True
    assert "today" in by_iso["2026-11-02"]["accessName"]
    assert by_iso["2026-10-31"]["accessName"] == "Saturday 31 October, not in this month"


def test_chips_use_the_12_hour_clock(week_start) -> None:
    session = FakeSession("2026-11", deadlines(), clock_24h=False)
    session.today = "2026-11-04"
    rows, _ = read_cells(session)
    assert [chip["text"] for chip in chips(rows, "2026-11-05")] == [
        "Due 7:00 PM History essay",
        "Due French oral",
    ]
    assert [chip["kind"] for chip in chips(rows, "2026-11-05")] == ["due", "due"]
    assert [chip["text"] for chip in chips(rows, "2026-11-06")] == ["8:00 AM School"]
    assert chips(rows, "2026-11-06")[0]["kind"] == "plain"


def test_chips_use_the_24_hour_clock(week_start) -> None:
    session = FakeSession("2026-11", deadlines(), clock_24h=True)
    session.today = "2026-11-04"
    rows, _ = read_cells(session)
    assert chips(rows, "2026-11-05")[0]["text"] == "Due 19:00 History essay"
    assert chips(rows, "2026-11-06")[0]["text"] == "08:00 School"


def test_a_deadline_on_a_date_that_has_gone_says_overdue(week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    session.today = "2026-11-04"
    rows, _ = read_cells(session)
    assert chips(rows, "2026-11-03") == [{"text": "Overdue Reading", "kind": "overdue"}]
    session.today = "2026-11-03"
    rows, _ = read_cells(session)
    assert chips(rows, "2026-11-03") == [{"text": "Due Reading", "kind": "due"}]


def test_a_finished_deadline_is_not_overdue(week_start) -> None:
    data = deadlines()
    data["overdue"][0]["completed"] = True
    session = FakeSession("2026-11", data)
    session.today = "2026-11-04"
    rows, _ = read_cells(session)
    assert chips(rows, "2026-11-03") == [{"text": "Due Reading", "kind": "due"}]


def test_study_time_shares_are_minutes_over_three_hours(week_start) -> None:
    data = snapshot(
        "2026-11",
        {
            "2026-11-04": {
                "in_month": True,
                "blocks": [
                    {
                        "id": "a",
                        "title": "Essay",
                        "start": "18:00",
                        "duration_min": 60,
                        "assignment_id": "essay",
                        "completed": True,
                    },
                    {
                        "id": "b",
                        "title": "Maths",
                        "start": "19:30",
                        "duration_min": 120,
                        "assignment_id": "maths",
                    },
                ],
            }
        },
    )
    rows, _ = read_cells(FakeSession("2026-11", data))
    row = next(item for item in rows if item["iso"] == "2026-11-04")
    assert row["plannedMin"] == 180
    assert row["completedMin"] == 60
    assert row["plannedShare"] == pytest.approx(1.0)
    assert row["completedShare"] == pytest.approx(60 / 180)
    assert row["lines"][-1] == "3 h homework planned · 1 h completed"
