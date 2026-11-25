# ruff: noqa: F811
"""What Plan my homework says about its result on the Material week: the notice's words and counts, the
homework
drawer's list of what has no time, the notice that offers Find a new time when a commitment lands over planned
homework, and the line after Replan all."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.controller import plan_sentence  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)
from desktop.tests.week.support_material import _bridge, _pump, _qml, _repeater_texts, _snack  # noqa: E402
from desktop.tests.week.support_material_page import fresh_material  # noqa: E402


def _friday_noon(window: NativeWindow) -> str:
    return f"{(date.fromisoformat(window.session.week_start) + timedelta(days=4)).isoformat()}T12:00"


def _poster_that_does_not_fit(window: NativeWindow, qapp: QApplication) -> None:
    """Ten hours due Friday noon, from a Thursday 19:00 clock: there is no room before then."""
    window.session.add_homework(
        {
            "id": "poster",
            "title": "Science fair poster",
            "due": _friday_noon(window),
            "estimate_min": 600,
            "revision": 0,
        }
    )
    window.session.save()
    settled(qapp, window)


def test_a_real_solve_explains_itself_once(qapp: QApplication, window: NativeWindow) -> None:
    """Driven through the real solver. When there is something to say the notice says it and the homework
    drawer keeps the card with its reason; reading the week again does not say it a second time."""
    root = fresh_material(qapp, window)
    _poster_that_does_not_fit(window, qapp)
    session = window.session
    _bridge(window).week.plan()
    wait_until(qapp, lambda: session.trace is not None and not session.busy and _snack(window) != "")
    _pump(qapp)
    assert session.trace.get("unplaced"), "the fixture should give the solver something it cannot place"
    assert _snack(window) == "No homework was placed. 1 still needs a time."
    assert "Science fair poster" in _repeater_texts(root, "homeworkRows", "homeworkTitle")
    assert _qml(root, "homeworkCount").property("text") == "1"

    # Reading the week again is not a new plan.
    bridge = _bridge(window)
    bridge._clear_snack(bridge._snack)
    window._on_week()
    _pump(qapp)
    assert _snack(window) == ""


def test_the_drawer_counts_what_the_notice_counts(qapp: QApplication, window: NativeWindow) -> None:
    """The drawer counts the homework with no time, while the notice names the time still needed."""
    root = fresh_material(qapp, window)
    _poster_that_does_not_fit(window, qapp)
    session = window.session
    _bridge(window).week.plan()
    wait_until(qapp, lambda: session.trace is not None and not session.busy and _snack(window) != "")
    _pump(qapp)
    assert len(session.trace.get("placed") or []) > 1, "the trace also lists School"
    placed, waiting = session.plan_counts
    assert waiting == 1
    # The essay was given 18:45 when it was added, so this Plan places nothing new.
    assert _snack(window) == plan_sentence(placed, waiting) == "No homework was placed. 1 still needs a time."
    assert _qml(root, "homeworkCount").property("text") == str(waiting)


def test_a_commitment_over_planned_homework_offers_find_a_new_time(
    qapp: QApplication, window: NativeWindow
) -> None:
    fresh_material(qapp, window)
    window.session.add_block(
        {"id": "club", "title": "Club", "kind": "locked", "start": "18:00", "duration_min": 120, "days": [3]}
    )
    _pump(qapp)
    assert "History essay" in _snack(window)
    assert str(_bridge(window).property("snackAction")).lower() == "find a new time"


def test_every_homework_that_lost_its_time_is_named_on_the_notice(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The notice named the first note only, so a second assignment that lost its time went unnamed while Find
    a new time moved it too."""
    fresh_material(qapp, window)
    notes = [
        {"block_id": "a", "message": "Math worksheet no longer fits Monday at 15:15: Club is there now."},
        {"block_id": "b", "message": "English essay no longer fits Monday at 15:45: Club is there now."},
    ]
    window._on_plan_conflicts(notes)
    _pump(qapp)
    shown = _snack(window)
    assert "Math worksheet" in shown and "English essay" in shown


def test_the_plan_notice_counts_homework_blocks(qapp: QApplication, window: NativeWindow) -> None:
    # The essay began at 18:45, before the clock's 19:00, so Replan all leaves it; this needs a time.
    fresh_material(qapp, window)
    due = sunday_due(window.session.week_start)
    window.session.add_homework({"id": "math", "title": "Math", "due": due, "estimate_min": 60})
    window.session.save()
    settled(qapp, window)
    window.session.solve(everything=True)
    wait_until(qapp, lambda: not window.session.busy and _snack(window).startswith("Placed"))
    _pump(qapp)
    # Material counts what Plan tried: one block placed of one; "Everything has a time." is the drawer's.
    assert _snack(window) == "Placed 1 of 1 homework sessions"
    assert _qml(_root(window), "homeworkEmptyText").property("text") == "Everything has a time."


def _root(window: NativeWindow):
    return window._material_page.root


def _cut_the_essay_to(qapp: QApplication, window: NativeWindow, minutes: int) -> None:
    """The student shaped the History essay by hand: pinned, `minutes` long, saved."""
    session = window.session
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    essay["duration_min"] = minutes
    essay["pinned"] = True
    essay["start"] = "19:30"
    session._touch()
    session.save()
    settled(qapp, window)
    # The server's count of what the homework still needs follows the save, as it does in the app.
    wait_until(qapp, lambda: session.assignments["essay"].get("unplanned_min") == 60 - minutes)


@pytest.mark.parametrize(
    ("minutes", "said", "left"),
    [
        # 60 - 5 = 55: Plan places 45 (three quarter hours) and 10 minutes have no session.
        (
            5,
            "Placed 1 of 1 homework sessions. History essay still has 10 min with no time.",
            [("History essay", 10)],
        ),
        # 60 - 15 = 45: Plan places all 45. Nothing is missing, so nothing is said to be.
        (15, "Placed 1 of 1 homework sessions", []),
        # 60 - 20 = 40: places 30, 10 left.
        (
            20,
            "Placed 1 of 1 homework sessions. History essay still has 10 min with no time.",
            [("History essay", 10)],
        ),
    ],
)
def test_the_plan_notice_names_the_minutes_it_could_not_place(
    qapp: QApplication, window: NativeWindow, minutes: int, said: str, left: list[tuple[str, int]]
) -> None:
    """Expected values are worked out from the requirement: the essay is 60 minutes, the student cut one
    session to `minutes`, and Plan places only whole quarter hours of the 60 - `minutes` still to do. The
    notice counts what Plan tried and names any homework with minutes that have no time."""
    fresh_material(qapp, window)
    _cut_the_essay_to(qapp, window, minutes)
    window.session.solve()
    wait_until(qapp, lambda: not window.session.busy and _snack(window) == said)
    _pump(qapp)
    kept = next(block for block in window.session.blocks if block.get("pinned"))
    assert (kept["duration_min"], kept["start"], kept["days"]) == (minutes, "19:30", [3])
    assert _snack(window) == said
    assert window.session.plan_remainders == left


def test_what_is_too_short_for_plan_is_counted_in_minutes(qapp: QApplication, window: NativeWindow) -> None:
    """60 - 50 = 10: under a quarter hour, so there is nothing for Plan to place; the line Plan gives when it
    finds nothing new counts the 10 minutes."""
    fresh_material(qapp, window)
    _cut_the_essay_to(qapp, window, 50)
    window.session.solve()
    wait_until(
        qapp, lambda: not window.session.busy and window.session.message == "10 min still needs a time"
    )
    kept = next(block for block in window.session.blocks if block.get("pinned"))
    assert (kept["duration_min"], kept["start"], kept["days"]) == (50, "19:30", [3])
    assert window.session.plan_remainders == []


def test_the_plan_key_with_too_short_minutes_left_says_how_many(
    qapp: QApplication, window: NativeWindow
) -> None:
    fresh_material(qapp, window)
    _cut_the_essay_to(qapp, window, 50)
    _bridge(window).plan()
    settled(qapp, window)
    _pump(qapp)
    assert _snack(window) == "10 min still needs a time"
