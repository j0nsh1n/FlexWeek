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


def test_homework_that_ended_unfinished_is_not_marked_done(qapp: QApplication) -> None:
    """Thursday 19:00. The essay's 16:00 to 17:00 is over and it is not finished: it is Missed, and drawn
    like work still to do, not dimmed as the finished Math session and School are. The next thing ahead, not
    the missed one, is Up next."""
    day = [
        block("school", "locked", [3], "08:00", 390),
        block("essay-1", "flexible", [3], "16:00", 60, assignment_id="essay"),
        block("math-1", "flexible", [3], "17:30", 30, assignment_id="math", completed=True, completed_day=3),
        block("chem-1", "flexible", [3], "20:00", 90, assignment_id="chem"),
    ]
    assert rows(shown(qapp, "19:00", day, homework=HOMEWORK)) == [
        ("08:00–14:30", "School", "6 h 30 min", "Done", "past"),
        ("16:00–17:00", "Essay-1", "1 h", "Missed", ""),
        ("17:30–18:00", "Math-1", "30 min", "Done", "past"),
        ("20:00–21:30", "Chem-1", "1 h 30 min", "Up next", ""),
    ]


def test_homework_still_to_come_or_on_now_keeps_its_tags(qapp: QApplication) -> None:
    day = [block("essay-1", "flexible", [3], "18:30", 60, assignment_id="essay")]
    assert rows(shown(qapp, "19:00", day, homework=HOMEWORK)) == [
        ("18:30–19:30", "Essay-1", "1 h", "Now", "now"),
    ]
    assert rows(shown(qapp, "17:00", day, homework=HOMEWORK)) == [
        ("18:30–19:30", "Essay-1", "1 h", "Up next", ""),
    ]
