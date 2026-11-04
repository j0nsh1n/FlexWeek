"""The Material month's bridge: which dates it draws, the words on each chip, and its actions.

Dates are worked out from the calendar (1 November 2026 is a Sunday), not read off the code.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from desktop.native.material import bridge_month  # noqa: E402
from desktop.native.material.bridge_month import MonthBridge, read_cells  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    existing = QApplication.instance()
    if existing is None:
        return QApplication(["flexweek-material-month"])
    if not isinstance(existing, QApplication):
        pytest.fail("Month tests need QApplication; a different Qt application is already running")
    return existing


class Shell(QObject):
    """The part of the bridge above the month: a changed signal and the page change."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.pages: list[str] = []

    def showPage(self, name: str) -> None:  # noqa: N802 - the name QML calls
        self.pages.append(name)


class FakeSession:
    def __init__(self, month: str, snapshot: dict | None, clock_24h: bool = False) -> None:
        self.account = {"id": "a"}
        self.preferences = {"clock_24h": clock_24h}
        self.week_start = ""
        self.planner_view = "month"
        self.selected_month: str | None = month
        self.month_data = snapshot
        self.today = "2026-11-02"
        self.calls: list[tuple] = []

    def now_ms(self) -> int:
        return 0

    def today_iso(self) -> str:
        return self.today

    def open_month(self, month: str | None = None) -> None:
        self.calls.append(("open_month", month))
        self.planner_view = "month"

    def shift_month(self, amount: int) -> None:
        self.calls.append(("shift_month", amount))

    def open_day(self, iso_day: str) -> None:
        self.calls.append(("open_day", iso_day))
        self.planner_view = "day"

    def built_week(self) -> None:
        return None

    def unsaved_weeks(self) -> dict:
        return {}


def snapshot(month: str, days: dict[str, dict] | None = None, **extra: list) -> dict:
    return {"month": month, "days": [{"date": iso, **body} for iso, body in (days or {}).items()], **extra}


def isos(rows: list[dict]) -> list[str]:
    return [row["iso"] for row in rows]


def bridge_for(session: FakeSession) -> tuple[MonthBridge, Shell]:
    shell = Shell()
    month = MonthBridge(SimpleNamespace(session=session), shell)
    month.reload()
    return month, shell


@pytest.fixture
def week_start(monkeypatch: pytest.MonkeyPatch):
    def choose(value: str) -> None:
        monkeypatch.setattr("desktop.native.hours.month.week_starts_on", lambda: value)
        monkeypatch.setattr(bridge_month, "week_starts_on", lambda: value)

    choose("monday")
    return choose


def test_the_month_app_fixture_can_build_a_widget(app: QApplication) -> None:
    """QWidget tests that share this process need QApplication, not QCoreApplication."""
    assert isinstance(app, QApplication)
    widget = QWidget()
    label = QLabel("month fixture", widget)
    try:
        widget.show()
        assert widget.isVisible()
        assert label.text() == "month fixture"
    finally:
        widget.close()
        widget.deleteLater()


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


def deadlines() -> dict:
    return snapshot(
        "2026-11",
        {
            "2026-11-05": {"in_month": True, "due_ids": ["essay", "oral"]},
            "2026-11-03": {"in_month": True, "due_ids": ["late"]},
            "2026-11-06": {
                "in_month": True,
                "blocks": [{"id": "school", "title": "School", "start": "08:00", "duration_min": 390}],
            },
        },
        deadlines=[
            {"id": "essay", "title": "History essay", "category": "assignments", "due": "2026-11-05T19:00"},
            {"id": "oral", "title": "French oral", "category": "assignments", "due": "2026-11-05"},
        ],
        overdue=[{"id": "late", "title": "Reading", "category": "assignments", "due": "2026-11-03"}],
    )


def chips(rows: list[dict], iso: str) -> list[dict]:
    row = next(item for item in rows if item["iso"] == iso)
    return json.loads(row["chipsJson"])


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


def test_the_study_switch_starts_off_and_only_changes_the_screen(app, week_start) -> None:
    month, _ = bridge_for(FakeSession("2026-11", snapshot("2026-11")))
    assert month.showStudyTime is False
    month.setShowStudyTime(True)
    assert month.showStudyTime is True
    month.setShowStudyTime(False)
    assert month.showStudyTime is False


def test_picking_a_date_opens_its_bar_and_picking_it_again_closes_it(app, week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    session.today = "2026-11-04"
    month, _ = bridge_for(session)
    assert month.barOpen is False
    month.selectDate("2026-11-05")
    assert month.barOpen is True
    assert month.selectedIso == "2026-11-05"
    assert month.heading == "Thursday 5 November"
    assert month.lines.rowCount() == 2
    month.selectDate("2026-11-05")
    assert month.barOpen is False
    month.selectDate("2026-11-30")
    month.closeDate()
    assert month.barOpen is False
    month.selectDate("2030-01-01")
    assert month.barOpen is False


def test_an_empty_date_says_nothing_planned(app, week_start) -> None:
    month, _ = bridge_for(FakeSession("2026-11", snapshot("2026-11")))
    month.selectDate("2026-11-10")
    assert month.heading == "Tuesday 10 November"
    assert [month.lines.data(month.lines.index(row, 0), 257) for row in range(month.lines.rowCount())] == [
        "Nothing planned"
    ]


def test_open_day_goes_to_that_date_through_the_shell(app, week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    month, shell = bridge_for(session)
    month.openDay()
    assert session.calls == [] and shell.pages == []
    month.selectDate("2026-11-05")
    month.openDay()
    assert session.calls == [("open_day", "2026-11-05")]
    assert shell.pages == ["day"]


def test_a_date_that_leaves_the_grid_closes_its_bar(app, week_start) -> None:
    session = FakeSession("2026-11", deadlines())
    month, _ = bridge_for(session)
    month.selectDate("2026-11-05")
    session.selected_month = "2027-02"
    session.month_data = snapshot("2027-02")
    month.reload()
    assert month.barOpen is False
    assert isos(month.cellRows)[0] == "2027-02-01"


def test_previous_and_next_ask_the_session_to_move_the_month(app, week_start) -> None:
    session = FakeSession("2026-11", snapshot("2026-11"))
    month, _ = bridge_for(session)
    month.nextMonth()
    month.previousMonth()
    assert session.calls == [("shift_month", 1), ("shift_month", -1)]
    session.planner_view = "week"
    month.nextMonth()
    assert session.calls[-2:] == [("open_month", None), ("shift_month", 1)]
