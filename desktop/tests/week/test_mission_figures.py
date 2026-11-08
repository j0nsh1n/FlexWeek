"""Mission control's four figures: what is planned, due, free and focused."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFrame, QLabel  # noqa: E402

from desktop.tests.day.support_mission import BLOCKS, HOMEWORK, block, figure, shown, table_rows  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-mission-figures-test"])


def test_the_four_figures_say_what_is_planned_due_free_and_focused(qapp: QApplication) -> None:
    """Thursday 13:40. Planned today is the day's homework: the essay at 18:45, the chem report at
    20:00 and the finished maths at 21:30, which is still on the day. Due this week is homework still
    to do: the maths was finished. Free time runs to 22:00 around School, Dinner and both homework
    still to do, and counts the finished maths as free: 500 minutes, less School's 50 to 14:30,
    Dinner's 30, the essay's 60 and the chem report's 90. No focus has been timed."""
    finished = block(
        "math-2", "flexible", [3], "21:30", 30, assignment_id="math", completed=True, completed_day=3
    )
    view = shown(qapp, blocks=[*BLOCKS, finished])
    assert figure(view, "missionPlanned") == ("3 h", "Essay-1 at 18:45")
    assert figure(view, "missionDue") == ("3", "2 placed, 1 not placed yet")
    assert figure(view, "missionFree") == ("4 h 30 min", "Until 22:00")
    assert figure(view, "missionFocus") == ("0 min", "None yet this week")
    cards = view.findChild(QFrame, "missionStrip").cards
    labels = [card.findChild(QLabel, "missionLabel").text() for card in cards]
    assert labels == ["Planned today", "Due this week", "Free time left today", "Focus minutes"]


def test_focus_minutes_are_what_the_timer_credited_to_this_weeks_homework(qapp: QApplication) -> None:
    homework = {**HOMEWORK, "chem": {**HOMEWORK["chem"], "focus_minutes": 35}}
    view = shown(qapp, homework=homework)
    assert figure(view, "missionFocus") == ("35 min", "On this week's homework")


def test_the_focus_figure_says_a_timer_is_running_instead_of_none_yet(qapp: QApplication) -> None:
    """Audit X5: a session was running and the figure said "None yet this week". The minutes stay
    those already credited; the line says what the timer is doing."""
    assert figure(shown(qapp, focus="focusing"), "missionFocus") == ("0 min", "Focusing now")
    assert figure(shown(qapp, focus="paused"), "missionFocus") == ("0 min", "Focus paused")
    assert figure(shown(qapp, focus="break"), "missionFocus") == ("0 min", "On a break")
    homework = {**HOMEWORK, "chem": {**HOMEWORK["chem"], "focus_minutes": 35}}
    credited = shown(qapp, homework=homework, focus="focusing")
    assert figure(credited, "missionFocus") == ("35 min", "Focusing now")


def test_another_week_has_no_today_to_count_from(qapp: QApplication) -> None:
    view = shown(qapp, today=None)
    for name in ("missionPlanned", "missionFree"):
        assert figure(view, name) == ("–", "Today is in another week.")
    assert figure(view, "missionDue") == ("3", "2 placed, 1 not placed yet")
    table = view.findChild(QFrame, "missionDeadlines")
    columns = [label.text() for label in table.findChildren(QLabel, "missionColumn")]
    assert columns == ["Homework", "Needs", "Due"]
    assert [row[2] for row in table_rows(view)] == ["Thu 17 Sep", "Fri 18 Sep", "Sun 20 Sep"]
