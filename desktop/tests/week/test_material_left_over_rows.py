"""Overdue and left-over homework on the Material week, as the student reads and uses it: the Unfinished
sheet's rows, the week as a list, the drawer and the focus list, and a deadline passing. Held-clock
scenario: Bio reading placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, clock
Saturday 10:00."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from backend.tests.fake_clock import CLOCK
from desktop.native.weekmodel import range_label
from desktop.tests.planner.support import FRIDAY, WEDNESDAY, left_in_week_one, overdue_this_week
from desktop.tests.week.support_material import (
    _bridge,
    _named,
    _pump,
    _qml,
    _show_material,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _short(day: date) -> str:
    return f"{day.strftime('%a')} {day.day} {day.strftime('%b')}"


def test_the_unfinished_sheet_names_each_homework_with_its_time_left_due_date_and_why(qapp, window) -> None:
    left_in_week_one(qapp, window)
    root = _show_material(qapp, window)
    sheets = _bridge(window).sheets
    sheets.openUnfinished()
    _pump(qapp, 40)
    assert sheets.kind == "unfinished"
    row = next(item for item in sheets.form["rows"] if item["id"] == "lab")
    due = date.fromisoformat(window.session.assignments["lab"]["due"][:10])
    assert row["title"] == "Lab report"
    assert row["detail"] == f"1 h left · due {_short(due)} · Left from last week"
    assert _named(root, "unfinishedRow"), "the sheet draws its rows"


@pytest.mark.xfail(
    strict=True,
    reason="product gap: the Widgets Unfinished row had a Start focus button; Material's Unfinished sheet "
    "has none (its rows offer Find a time and Delete)",
)
def test_an_unfinished_row_has_a_start_focus_button(qapp, window) -> None:
    left_in_week_one(qapp, window)
    root = _show_material(qapp, window)
    _bridge(window).sheets.openUnfinished()
    _pump(qapp, 40)
    assert _named(root, "focusUnfinished-lab"), "no Start focus on the row"


def test_the_overdue_row_is_still_there_while_the_unfinished_sheet_is_open(qapp, window) -> None:
    """The Widgets chip hid while its list was open; Material's row stays under the sheet, whose scrim covers
    it. The row comes and goes with the homework, not with the sheet."""
    overdue_this_week(qapp, window)
    root = _show_material(qapp, window)
    _pump(qapp)
    assert _qml(root, "leftOverRow").property("visible") is True
    sheets = _bridge(window).sheets
    sheets.openUnfinished()
    _pump(qapp, 40)
    window.session.week_changed.emit()
    settled(qapp, window)
    assert _qml(root, "leftOverRow").property("visible") is True
    sheets.closeSheet()
    _pump(qapp, 40)
    assert _qml(root, "leftOverRow").property("visible") is True


def test_the_overdue_focus_row_starts_focus_credits_the_homework_and_survives_a_restart(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    session.preferences["timer_work_min"] = 25
    row = next(item for item in session.focus_tasks() if item["title"] == "Bio reading, overdue")
    assert row["id"] == "bio"
    assert session.start_focus(row["id"], row["day"]) is True
    assert session.focus["assignmentId"] == "bio"
    session._reset_focus(persist=False)
    session._restore_focus()
    assert session.focus["title"] == "Bio reading"
    session.advance_focus(completed=True)
    settled(qapp, window)
    session.reload()
    settled(qapp, window)
    assert session.assignments["bio"]["focus_minutes"] == 25
    assert session.assignments["bio"]["focus_sessions"] == 1
    assert session.assignments["bio"]["completed"] is False


def _bio_on_wednesday(qapp, window) -> date:
    session = window.session
    friday = date.fromisoformat(session.week_start) + timedelta(days=FRIDAY)
    # A hand move to a day already past is refused, so the clock is early in the week while it is placed.
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(hours=8))
    session.add_homework(
        {
            "id": "bio",
            "title": "Bio reading",
            "due": friday.isoformat() + "T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "bio")
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15)
    session.save()
    settled(qapp, window)
    return friday


def test_the_deadline_passing_makes_the_homework_overdue_in_the_focus_list_and_says_so_once(
    qapp, window, monkeypatch
) -> None:
    friday = _bio_on_wednesday(qapp, window)
    session = window.session
    _show_material(qapp, window)
    announcements = []
    monkeypatch.setattr(
        "desktop.native.window.announce",
        lambda widget, words, assertive=False: announcements.append((widget, words, assertive)),
    )
    before = datetime.combine(friday, datetime.min.time()).replace(hour=23, minute=58)
    CLOCK.set(before)
    session.week_changed.emit()
    settled(qapp, window)
    assert not session.unfinished()
    assert 0 < window._deadline_tick.remainingTime() <= 61_000
    CLOCK.set(before + timedelta(minutes=3))
    window._deadline_tick.timeout.emit()
    settled(qapp, window)
    _pump(qapp)
    assert session.unfinished()[0]["left_over_state"] == "overdue"
    assert any(item["title"] == "Bio reading, overdue" for item in session.focus_tasks())
    # The hidden Widgets chip also announces; Material's screen is the window itself.
    said = [item for item in announcements if item[0] is window and item[1] == "1 overdue"]
    assert len(said) == 1 and said[0][2] is False
    window._deadline_changed()
    settled(qapp, window)
    again = [item for item in announcements if item[0] is window and item[1] == "1 overdue"]
    assert again == said, "said once"


def test_the_week_list_row_says_overdue_with_the_due_date(qapp, window) -> None:
    overdue_this_week(qapp, window)
    _show_material(qapp, window)
    sheets = _bridge(window).sheets
    sheets.openWeekList()
    _pump(qapp, 40)
    rows = [item["words"] for item in sheets.form["rows"] if item.get("type") == "item"]
    due = date.fromisoformat(window.session.assignments["bio"]["due"][:10])
    due_words = f"Overdue, was due {_short(due)}"
    times = range_label(15 * 60 + 15, 16 * 60 + 15)
    expected = f"Wednesday: Bio reading, {times} · {due_words} · Pinned"
    assert [row for row in rows if row.startswith("Wednesday: Bio reading, ")] == [expected]
    # Only the late, hand-placed block says so: the other rows carry neither word.
    assert [row for row in rows if "Overdue" in row or "Pinned" in row] == [expected]


@pytest.mark.xfail(
    strict=True,
    reason="product gap: a deadline passing refreshes the Widgets pages only (_deadline_changed); "
    "Material's overdue row keeps its old words until something else changes the week",
)
def test_the_deadline_passing_updates_materials_overdue_row(qapp, window) -> None:
    friday = _bio_on_wednesday(qapp, window)
    root = _show_material(qapp, window)
    before = datetime.combine(friday, datetime.min.time()).replace(hour=23, minute=58)
    CLOCK.set(before)
    window.session.week_changed.emit()
    settled(qapp, window)
    CLOCK.set(before + timedelta(minutes=3))
    window._deadline_tick.timeout.emit()
    settled(qapp, window)
    _pump(qapp)
    assert _qml(root, "leftOverWords").property("text") == "1 overdue"
