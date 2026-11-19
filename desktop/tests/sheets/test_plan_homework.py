"""Plan places homework: it never puts anything before now, it leaves homework whose time has passed
where it is, it says so when the week is over, and the drawer counts the homework without a time. Run on the
Material week."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import date_for_day, sunday_due
from desktop.native.controller import plan_sentence
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, qml
from desktop.tests.sheets.support_plan import (
    PAST_WEEK,
    TOO_LATE,
    session_of,
    settled,
    thursday_iso,
    window,  # noqa: F401
)
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import _bridge, _snack
from desktop.tests.week.support_material_page import fresh_material
from desktop.tests.window_support import qapp  # noqa: F401


def test_nothing_placed_says_nothing_placed_not_planned_zero() -> None:
    assert plan_sentence(0, 1) == "Nothing placed. 1 with no time yet."
    assert plan_sentence(0, 2) == "Nothing placed. 2 with no time yet."
    assert plan_sentence(1, 1) == "Placed 1 homework block. 1 with no time yet."
    assert plan_sentence(2, 1) == "Placed 2 homework blocks. 1 with no time yet."
    assert plan_sentence(3, 0) == "Placed 3 homework blocks."


def test_plan_on_a_thursday_leaves_monday_to_wednesday_and_the_hours_before_now_alone(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    wednesday = date_for_day(session.week_start, 2)
    session.add_homework(
        {
            "id": "reading",
            "title": "Reading log",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "energy": "high",
            "revision": 0,
        },
        days=[3],
    )
    session.add_homework(
        {"id": "chem", "title": "Chem lab report", "due": wednesday, "estimate_min": 60, "revision": 0}
    )
    session.save()
    settled(qapp, window)
    before = {block["id"]: (block["days"], block.get("start")) for block in session.blocks}
    session.solve()
    settled(qapp, window)

    after = {block["id"]: (block["days"], block.get("start")) for block in session.blocks}
    moved = {key: value for key, value in after.items() if before.get(key) != value}
    assert moved, "the plan placed something"
    for key, (days, start) in moved.items():
        assert start is not None and (days[0], start) >= (3, "10:00"), f"{key} planned at {days} {start}"
    assert session_of(window, "reading")["days"] == [3]
    assert session_of(window, "reading")["start"] >= "10:00", "its morning is before now"
    assert session_of(window, "math")["days"][0] >= 3
    chem = session_of(window, "chem")
    assert not chem.get("start"), "due yesterday: there is no time left for it this week"
    assert session.needs_time[chem["id"]] == TOO_LATE


def test_replan_all_moves_homework_whose_time_has_passed(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """The clock is Thursday 10:00. Tuesday 15:00 was not done, so Replan all gives it a time from now on
    (it used to leave a passed time alone, which spec.md's "plans every unfinished session again" does
    not say)."""
    session = window.session
    math = session_of(window, "math")
    session.add_block({**math, "start": "15:00", "days": [1]})
    session.save()
    settled(qapp, window)
    assert not session_of(window, "math").get("pinned")
    fresh_material(qapp, window)
    _bridge(window).sheets.moreAction("replanAll")
    settled(qapp, window)
    math = session_of(window, "math")
    assert math.get("start"), "there is room before the deadline"
    assert (math["days"][0], math["start"]) >= (3, "10:00"), "Tuesday is gone; it is placed from now on"


def test_plan_it_as_i_add_it_starts_no_earlier_than_now(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "planning_style": "auto"}
    fresh_material(qapp, window)
    sheets = _bridge(window).sheets
    sheets.openHomework()
    sheets.setText("title", "Spanish vocab")
    pump(qapp, 20)
    sheets.save()
    wait_until(
        qapp, lambda: any(item["title"] == "Spanish vocab" for item in window.session.assignments.values())
    )
    settled(qapp, window)
    added = next(item for item in window.session.assignments.values() if item["title"] == "Spanish vocab")
    placed = session_of(window, added["id"])
    assert placed.get("start"), "placed as it was added"
    assert (placed["days"][0], placed["start"]) >= (3, "10:00")


def test_plan_on_a_week_that_is_over_places_nothing_and_says_so(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Plan asks about left-over homework first, in a Widgets sheet nothing answers here; none is left over.
    monkeypatch.setattr(window, "_unfinished_items", lambda: [])
    session = window.session
    last = (date.fromisoformat(session.week_start) - timedelta(days=7)).isoformat()
    session.load_week(last)
    wait_until(qapp, lambda: session.week_start == last and not session.busy)
    session.add_homework(
        {"id": "late", "title": "Old worksheet", "due": sunday_due(last), "estimate_min": 60, "revision": 0}
    )
    session.save()
    settled(qapp, window)
    fresh_material(qapp, window)
    _bridge(window).week.plan()
    wait_until(qapp, lambda: _snack(window) == PAST_WEEK, what=lambda: repr(_snack(window)))
    settled(qapp, window)
    assert not session_of(window, "late").get("start")


def test_plan_on_a_week_that_is_over_does_not_ask_the_solver(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session refuses a week that is over before Plan talks to the solver. The engine also refuses,
    so the window test above still passes if this check is skipped."""
    session = window.session
    last = (date.fromisoformat(session.week_start) - timedelta(days=7)).isoformat()
    session.load_week(last)
    wait_until(qapp, lambda: session.week_start == last and not session.busy)
    said: list[str] = []
    monkeypatch.setattr(session, "_say", said.append)

    def no_solver(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Plan talked to the solver for a week that is over")

    monkeypatch.setattr(session.client, "request", no_solver)
    session.solve()
    assert said == [PAST_WEEK]


def test_the_drawer_and_the_notice_count_the_same_homework_without_a_time(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """The drawer said "Everything has a time." beside a notice saying "1 with no time yet". Plan with one
    project too long for what is left today: the notice counts it and so does the drawer, whose "Everything
    has a time." is hidden."""
    session = window.session
    session.add_homework(
        {
            "id": "project",
            "title": "Long project",
            "due": thursday_iso(window) + "T23:00",
            "estimate_min": 300,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    root = fresh_material(qapp, window)
    _bridge(window).week.plan()
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not session.busy)
    settled(qapp, window)
    pump(qapp)
    assert _snack(window) == "Placed 1 of 2"
    assert qml(root, "homeworkCount").property("text") == "1"
    assert qml(root, "homeworkEmpty").property("visible") is False
