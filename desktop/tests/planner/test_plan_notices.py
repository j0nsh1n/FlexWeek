# ruff: noqa: F811
"""What Plan my homework says about its result: the plan panel, the plan bar's counts, the notice that
offers Find a new time when a commitment lands over planned homework, and the toast after Replan all."""

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


def test_a_real_solve_explains_itself_once(qapp: QApplication, window: NativeWindow) -> None:
    """Driven through the real solver, not a fixture trace. The panel opens when there is something to
    say, and a later week load must not reopen it."""
    # Ten hours due at the start of the week: there is no room before that deadline, so the solver has
    # something to say. Given a comfortable week it says nothing, which is the point of it.
    window.session.add_homework(
        {
            "id": "poster",
            "title": "Science fair poster",
            "due": f"{window.session.week_start}T08:00",
            "estimate_min": 600,
            "revision": 0,
        }
    )
    window.session.save()
    settled(qapp, window)
    window.session.solve()
    wait_until(qapp, lambda: window.session.trace is not None and not window.session.busy)
    qapp.processEvents()
    assert window.session.trace is not None
    said = [window.plan_review.list.item(i).text() for i in range(window.plan_review.list.count())]
    trace = window.session.trace
    assert trace.get("unplaced"), "the fixture should give the solver something it cannot place"
    assert said, "the solver had something to say and the panel showed nothing"
    assert any("Science fair poster" in line for line in said)
    assert window.plan_review.isVisible() is True

    # Reading the week again is not a new plan.
    window.plan_review.hide()
    window._on_week()
    qapp.processEvents()
    assert window.plan_review.isVisible() is False


def test_the_plan_bar_counts_what_the_toast_counts(qapp: QApplication, window: NativeWindow) -> None:
    """The bar counts the unplaced homework, while the toast names time still needed."""
    session = window.session
    session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "category": "class",
         "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]}
    )  # fmt: skip
    due = f"{(date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat()}T23:59"
    session.add_homework(
        {"id": "essay", "title": "History essay", "due": due, "estimate_min": 60, "revision": 0}
    )
    # Ten hours due at the week's start: there is no room for it, so the bar has something to say.
    session.add_homework(
        {"id": "poster", "title": "Science fair poster",
         "due": f"{session.week_start}T08:00", "estimate_min": 600, "revision": 0}
    )  # fmt: skip
    session.save()
    settled(qapp, window)
    session.solve()
    wait_until(qapp, lambda: session.trace is not None and not session.busy)
    qapp.processEvents()
    assert len(session.trace.get("placed") or []) > 1, "the trace also lists School"
    placed, waiting = session.plan_counts
    assert waiting == 1
    # The toast counts homework placed by this Plan and the homework with no time yet. The essay was
    # given 18:45 when it was added, so this Plan places nothing new.
    assert window.toast.text() == "Nothing placed. 1 with no time yet."
    assert window.plan_review.isVisible()
    assert window.plan_review.heading.text() == plan_sentence(placed, waiting)


def test_a_commitment_over_planned_homework_offers_find_a_new_time(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "start": "18:00",
            "duration_min": 120,
            "days": [3],
        }
    )
    qapp.processEvents()
    assert window.toast.button.isVisible()
    assert window.toast.button.text() == "Find a new time"
    assert "History essay" in window.toast.text()


def test_a_conflict_is_said_once_on_the_notice_not_again_in_a_toast(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.add_block(
        {"id": "club", "title": "Club", "kind": "locked", "start": "18:00", "duration_min": 120, "days": [3]}
    )
    qapp.processEvents()
    assert window.toast.button.isVisible()
    assert window.toast.button.text() == "Find a new time", "said once, with its button"


def test_every_homework_that_lost_its_time_is_named_on_the_notice(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The notice showed the first note only, so a second assignment that lost its time went unnamed
    while Find a new time moved it too."""
    notes = [
        {"block_id": "a", "message": "Math worksheet no longer fits Monday at 15:15: Club is there now."},
        {"block_id": "b", "message": "English essay no longer fits Monday at 15:45: Club is there now."},
    ]
    window._on_plan_conflicts(notes)
    qapp.processEvents()
    shown = window.toast.text()
    assert "Math worksheet" in shown and "English essay" in shown


def test_the_plan_notice_counts_homework_blocks(qapp: QApplication, window: NativeWindow) -> None:
    # The essay began at 18:45, before the clock's 19:00, so Replan all leaves it; this needs a time.
    due = sunday_due(window.session.week_start)
    window.session.add_homework({"id": "math", "title": "Math", "due": due, "estimate_min": 60})
    window.session.save()
    settled(qapp, window)
    window.session.solve(everything=True)
    wait_until(qapp, lambda: not window.session.busy)
    qapp.processEvents()
    # Plan's toast counts the blocks it placed; "Everything has a time." is the sidebar's.
    assert window.toast.text() == "Placed 1 homework block."
    assert " of " not in window.toast.text()
