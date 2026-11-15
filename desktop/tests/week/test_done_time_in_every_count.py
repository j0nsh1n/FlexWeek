"""A homework's done time (the larger of its focus minutes and its minutes ticked done) comes off in every
count the desktop shows or acts on: Spread over days in both looks and the server's spread preview, and
it stays through an edit made in a week that holds none of the homework's sessions.

The cases use the Lab report (2 hours, due Sunday of the open week) with one hour ticked done, against
the same hour left unticked."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.material.sheet_homework import HomeworkDraft
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.test_unfinished_from_last_week import lab_sessions, left_in_week_one
from desktop.tests.window_support import qapp, settled  # noqa: F401


@pytest.fixture(autouse=True)
def reset_clock():
    CLOCK.reset()
    yield
    CLOCK.reset()


@pytest.mark.parametrize("ticked", [False, True])
def test_spread_offers_only_the_time_not_yet_done(
    qapp: QApplication, window: NativeWindow, ticked: bool
) -> None:
    # 120 min with one hour ticked done: both looks' sheets and the server's preview spread the other hour.
    # Left unticked, that hour's session has passed: the sheets offer all 120 (Spread over days replaces
    # every open time), and the preview, which counts what the stored sessions hold, the other 60.
    session = window.session
    week = session.week_start
    due = (datetime.fromisoformat(week) + timedelta(days=6)).date().isoformat() + "T23:59"
    session.add_homework({"id": "lab", "title": "Lab report", "estimate_min": 120, "due": due, "revision": 0})
    session.save()
    settled(qapp, window)
    hour = lab_sessions(window)[0]
    done = {"completed": True, "completed_day": 0} if ticked else {}
    session.add_block({**hour, "duration_min": 60, "days": [0], "start": "06:00", **done})
    session.save()
    settled(qapp, window)
    body = deepcopy(session.assignments["lab"])
    draft = HomeworkDraft(session, deepcopy(body))
    material = sum(item["duration_min"] for item in draft._spread_figures()[2])
    dialog = HomeworkDialog(window, deepcopy(body))
    try:
        widgets = sum(item["duration_min"] for item in dialog._spread_figures()[2])
    finally:
        dialog.reject()
        dialog.deleteLater()
    session.preview_spread("lab", 60, week)
    wait_until(qapp, lambda: not session.busy)
    settled(qapp, window)
    preview = session.spread_preview
    previewed = sum(row["block"]["duration_min"] for row in preview["rows"]) if preview else 0
    sheets = 60 if ticked else 120
    assert (material, widgets, previewed) == (sheets, sheets, 60)


@pytest.mark.parametrize("ticked", [False, True])
def test_an_edit_keeps_the_done_time_from_earlier_weeks(
    qapp: QApplication, window: NativeWindow, ticked: bool
) -> None:
    # The Lab report (now 120 min) had its hour in week 1, ticked done or not; week 2 holds none of it.
    # Editing its notes in week 2 keeps what still needs a time: 60 when the hour was ticked, else 120.
    week1, week2 = left_in_week_one(qapp, window)
    session = window.session
    session.assignments["lab"]["estimate_min"] = 120
    session.dirty_assignments.add("lab")
    session.save()
    settled(qapp, window)
    session.load_week(week1)
    wait_until(qapp, lambda: session.week_start == week1 and not session.busy)
    settled(qapp, window)
    hour = lab_sessions(window)[0]
    done = {"completed": True, "completed_day": hour["days"][0]} if ticked else {}
    session.add_block({**hour, "completed": ticked, **done})
    session.save()
    settled(qapp, window)
    session.load_week(week2)
    wait_until(qapp, lambda: session.week_start == week2 and not session.busy)
    settled(qapp, window)
    assert lab_sessions(window) == []
    needed = 60 if ticked else 120
    assert sum(row["minutes"] for row in session.homework_time_needed()) == needed
    session.add_homework({**session.assignments["lab"], "notes": "Cite sources"})
    assert sum(row["minutes"] for row in session.homework_time_needed()) == needed
    assert [block["duration_min"] for block in lab_sessions(window)] == [needed]
