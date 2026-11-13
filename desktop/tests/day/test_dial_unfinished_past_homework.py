"""Day dial's list for homework whose time went by. Finished homework and fixed time that is over read
"Done"; a homework session that ended and was not finished must not, since it is still to do."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.tests.day.support_dial import rows, shown
    from desktop.tests.test_weekmodel import HOMEWORK, block


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-dial-unfinished"])


# Estimates as the planner reads them: each homework's minutes are what its sessions below sum to.
WORK = {
    "essay": {**HOMEWORK["essay"], "estimate_min": 60},
    "math": {**HOMEWORK["math"], "estimate_min": 30},
    "chem": {**HOMEWORK["chem"], "estimate_min": 90},
}


def _day() -> list[dict]:
    return [
        block("school", "locked", [3], "08:00", 390),
        block("essay-1", "flexible", [3], "16:00", 60, assignment_id="essay"),
        block("math-1", "flexible", [3], "17:30", 30, assignment_id="math", completed=True, completed_day=3),
        block("chem-1", "flexible", [3], "20:00", 90, assignment_id="chem"),
    ]


def test_homework_that_ended_unfinished_is_not_marked_done(qapp: QApplication) -> None:
    """Thursday 19:00. The essay (60 min estimated, no focus) ended at 17:00 unfinished, so the planner
    calls it missed: the dial says Missed and draws it like work still to do, not dimmed as the finished
    Math session and School are. The next thing ahead, not the missed one, is Up next."""
    assert rows(shown(qapp, "19:00", _day(), homework=WORK)) == [
        ("08:00–14:30", "School", "6 h 30 min", "Done", "past"),
        ("16:00–17:00", "Essay-1", "1 h", "Missed", ""),
        ("17:30–18:00", "Math-1", "30 min", "Done", "past"),
        ("20:00–21:30", "Chem-1", "1 h 30 min", "Up next", ""),
    ]


def test_a_session_the_focus_timer_covered_still_reads_done(qapp: QApplication) -> None:
    """The essay's 60 min are all logged as focus time, so nothing is needed: the planner does not call
    its ended session missed, and the dial agrees: Done, drawn as over. It does not call a session
    Missed that a Replan all would leave alone."""
    covered = {**WORK, "essay": {**WORK["essay"], "focus_minutes": 60}}
    assert rows(shown(qapp, "19:00", _day(), homework=covered))[1] == (
        "16:00–17:00", "Essay-1", "1 h", "Done", "past",
    )  # fmt: skip


def test_a_pinned_session_that_ended_unfinished_still_reads_missed(qapp: QApplication) -> None:
    """No plan moves a pinned session, but it is unfinished and over, and the dial says so as before."""
    day = _day()
    day[1]["pinned"] = True
    assert rows(shown(qapp, "19:00", day, homework=WORK))[1] == (
        "16:00–17:00", "Essay-1", "1 h", "Missed", "",
    )  # fmt: skip


def test_homework_still_to_come_or_on_now_keeps_its_tags(qapp: QApplication) -> None:
    day = [block("essay-1", "flexible", [3], "18:30", 60, assignment_id="essay")]
    assert rows(shown(qapp, "19:00", day, homework=HOMEWORK)) == [
        ("18:30–19:30", "Essay-1", "1 h", "Now", "now"),
    ]
    assert rows(shown(qapp, "17:00", day, homework=HOMEWORK)) == [
        ("18:30–19:30", "Essay-1", "1 h", "Up next", ""),
    ]
