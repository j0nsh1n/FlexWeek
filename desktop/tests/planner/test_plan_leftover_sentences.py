# ruff: noqa: F811
"""The words Plan uses for homework minutes it could not give a time: the sentence itself, the "And N more"
tail, the line when what is left is too short for Plan, and the cases a hand-cut session, a finished
homework and a focus timer make. Expected values are worked out in each docstring."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.controller import left_sentence, plan_sentence  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)


def test_the_leftover_sentence_names_two_and_counts_the_rest() -> None:
    """Two are named with their minutes; three or more add "And N more." for the others. 600 - 5 = 595 is
    9 h 55 min; 20 min and 5 min stay in minutes."""
    one = [("History essay", 10)]
    two = [*one, ("Science fair poster", 595)]
    three = [*two, ("Math", 5)]
    five = [*three, ("Art", 20), ("Music", 5)]
    assert left_sentence([]) == ""
    assert left_sentence(one) == " History essay still has 10 min with no time."
    assert left_sentence(two) == (
        " History essay still has 10 min with no time. Science fair poster still has 9 h 55 min with no time."
    )
    assert left_sentence(three).endswith("with no time. And 1 more.")
    assert left_sentence(five).endswith("with no time. And 3 more.")
    assert "Math" not in left_sentence(five)
    assert plan_sentence(2, 0, three) == (
        "Placed 2 homework blocks. History essay still has 10 min with no time. "
        "Science fair poster still has 9 h 55 min with no time. And 1 more."
    )
    assert plan_sentence(0, 1, one) == (
        "Nothing placed. 1 with no time yet. History essay still has 10 min with no time."
    )


def _three_homework_each_missing_ten_minutes(qapp: QApplication, window: NativeWindow) -> None:
    """Three 60 minute homework, each with its one session cut by hand to 5 minutes on Friday and pinned.
    60 - 5 = 55: Plan places 45 of each and 10 minutes of each are in no session."""
    session = window.session
    due = sunday_due(session.week_start)
    for number, (key, title) in enumerate((("a", "Art"), ("b", "Biology"), ("c", "Chemistry"))):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60})
        block = next(item for item in session.blocks if item.get("assignment_id") == key)
        block.update(duration_min=5, pinned=True, start=f"1{number}:00", days=[4])
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(
        qapp, lambda: all(session.assignments[key].get("unplanned_min") == 55 for key in ("a", "b", "c"))
    )


def test_three_homework_with_minutes_left_name_two_and_count_one(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Each of three homework misses 10 minutes after Plan: two are named, "And 1 more." takes the third."""
    _three_homework_each_missing_ten_minutes(qapp, window)
    window.session.solve()
    wait_until(qapp, lambda: not window.session.busy and window.toast.text().startswith("Placed"))
    qapp.processEvents()
    assert window.toast.text() == (
        "Placed 3 homework blocks. Art still has 10 min with no time. "
        "Biology still has 10 min with no time. And 1 more."
    )
    assert window.session.plan_remainders == [("Art", 10), ("Biology", 10), ("Chemistry", 10)]


def test_a_finished_homework_has_no_minutes_left(qapp: QApplication, window: NativeWindow) -> None:
    """Essay cut to 5 (55 to do) and then ticked off: a finished homework needs nothing, whatever the cut."""
    session = window.session
    essay = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    essay.update(duration_min=5, pinned=True)
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 55)
    assert [item["minutes"] for item in session.homework_time_needed()] == [55]
    session.complete_homework("essay", True)
    settled(qapp, window)
    assert session.homework_time_needed() == []
    assert session.homework_remainders() == []
    assert session.minutes_left_for("essay") == 0


def test_a_focus_timer_shortens_what_is_still_needed(qapp: QApplication, window: NativeWindow) -> None:
    """60 minutes of homework with no session and 25 minutes of timer: 35 are still needed, counted at once
    even before the server's number is read again. Plan places 30 of them (two quarter hours) and names the
    5 that remain."""
    session = window.session
    due = sunday_due(session.week_start)
    session.add_homework({"id": "timer", "title": "Timer homework", "due": due, "estimate_min": 60})
    own = next(item["id"] for item in session.blocks if item.get("assignment_id") == "timer")
    session.delete_block(own)
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["timer"].get("unplanned_min") == 60)
    session.assignments["timer"]["focus_minutes"] = 25
    session.dirty_assignments.add("timer")
    assert [item["minutes"] for item in session.homework_time_needed()] == [35]
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["timer"].get("unplanned_min") == 35)
    session.solve()
    wait_until(qapp, lambda: not session.busy and window.toast.text().startswith("Placed"))
    qapp.processEvents()
    assert window.toast.text() == "Placed 1 homework block. Timer homework still has 5 min with no time."
    placed = [item for item in session.blocks if item.get("assignment_id") == "timer"]
    assert [item["duration_min"] for item in placed] == [30]


def test_what_is_too_short_for_plan_is_said_in_minutes(qapp: QApplication, window: NativeWindow) -> None:
    """Essay cut to 50 leaves 10 minutes, under the 15 Plan places: both ways of planning a homework say how
    many minutes are left instead of "fully planned". With nothing left at all they say the old sentences."""
    session = window.session
    essay = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    essay.update(duration_min=50, pinned=True)
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 10)

    assert session.plan_unfinished("essay") is None
    assert session.message == "History essay has 10 min left, less than the 15 minutes Plan places."
    session.plan_left(["essay"])
    assert session.message == "History essay has 10 min left, less than the 15 minutes Plan places."

    next(item for item in session.blocks if item.get("assignment_id") == "essay")["duration_min"] = 60
    session._touch()
    session.save()
    settled(qapp, window)
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 0)
    assert session.plan_unfinished("essay") is None
    assert session.message == "That homework is already fully planned."
    session.plan_left(["essay"])
    assert session.message == "That homework already has a time."
