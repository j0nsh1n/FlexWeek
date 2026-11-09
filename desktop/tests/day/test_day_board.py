"""What the Material Day and My day screens say about one day: counts, Up next and Done, status tags,
the free-time card, and which block Start focus opens.

Expected strings come from the spec (Jonathan's words) and from the clock set in each test, not from
reading the code's output. The colours of the rows are a picture (pictures/_myday_g01.py).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, datetime
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import CLOCK, START  # noqa: E402
from desktop.native.material.bridge_day import DayBridge  # noqa: E402
from desktop.native.material.day_board import board_for, read_flag  # noqa: E402
from desktop.native.weekmodel import Occurrence, set_clock_24h  # noqa: E402

TODAY = START.date()


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-day-board"])
    yield application


def _block(
    title: str,
    start: int,
    end: int,
    *,
    work: bool = False,
    done: bool = False,
    missed: bool = False,
    assignment: str | None = None,
    category: str = "class",
    pinned: bool = False,
    due: str | None = None,
    slack: str | None = None,
) -> Occurrence:
    return Occurrence(
        block_id=title.lower().replace(" ", "-"),
        title=title,
        category=category,
        day=3,
        start=start,
        end=end,
        work=work,
        done=done,
        missed=missed,
        assignment_id=assignment,
        due=due,
        slack=slack,
        pinned=pinned,
    )


def _board(items: list[Occurrence], minute: int, when: str = "today", nudges: bool = True):
    set_clock_24h(True)
    return board_for(items, minute=minute, when=when, nudges=nudges, dim=True, mode="light", on=TODAY)


SCHOOL = (8 * 60, 12 * 60)
ESSAY = (18 * 60 + 45, 19 * 60 + 45)
SOCCER = (16 * 60, 17 * 60 + 30)


def test_the_count_line_says_things_left_today() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER, category="exercise"), _block("Essay", *ESSAY)]
    assert _board(day, 15 * 60).left_line == "2 things left today"
    assert _board(day, 17 * 60 + 40).left_line == "1 thing left today"
    assert _board(day, 20 * 60).left_line == "Nothing left today"
    assert _board([], 9 * 60).left_line == "Nothing left today"


def test_lists_split_by_the_clock_and_by_finishing() -> None:
    essay = _block("Essay", *ESSAY, work=True, assignment="a1", due="2026-11-08T23:59")
    over = _block("Maths", 17 * 60, 18 * 60, work=True, done=True, assignment="a2")
    board = _board([_block("School", *SCHOOL), over, essay], 15 * 60)
    assert [row.title for row in board.up_next] == ["Essay"]
    assert [row.title for row in board.done] == ["School", "Maths"]
    assert board.ring_count == 1
    assert board.ring_share == pytest.approx(2 / 3)
    assert board.up_next[0].can_finish is True
    assert board.done[0].can_finish is False
    assert "Due" in board.up_next[0].subtitle
    assert board.up_next[0].subtitle.startswith("18:45–19:45")


def test_each_kind_of_row_wears_its_icon() -> None:
    day = [
        _block("School", *SCHOOL),
        _block("Soccer", *SOCCER, category="exercise"),
        _block("Essay", *ESSAY, work=True, assignment="a1", category="assignments"),
    ]
    set_clock_24h(True)
    board = board_for(day, minute=9 * 60, when="future", nudges=True, dim=True, mode="light", on=TODAY)
    assert [row.icon for row in board.up_next] == ["school", "schedule", "edit_note"]


def test_pinned_shows_in_the_row_note() -> None:
    board = _board([_block("Soccer", *SOCCER, pinned=True)], 9 * 60)
    assert board.up_next[0].subtitle == "16:00–17:30 · Pinned"


def test_status_tags_use_the_slack_words() -> None:
    """The three slack labels the week model already uses, plus none."""
    tight = _block("Essay", *ESSAY, work=True, assignment="a1", slack="tight")
    plenty = _block("Poster", 20 * 60, 21 * 60, work=True, assignment="a2", slack="ok")
    cutting = _block("Quiz", 21 * 60, 22 * 60, work=True, assignment="a3", slack="danger")
    board = _board([tight, plenty, cutting], 9 * 60)
    assert [(row.tag, row.tag_kind) for row in board.up_next] == [
        ("Tight", "tight"),
        ("Plenty of time", "plenty"),
        ("Cutting it close", "cutting"),
    ]
    finished = _block("Essay", *ESSAY, work=True, assignment="a1", done=True, slack="tight")
    done = _board([finished], 9 * 60)
    assert done.done[0].tag == ""
    assert done.done[0].tag_kind == ""


def test_plenty_of_time_is_never_due_within_24_hours() -> None:
    soon = _block(
        "Soon", 20 * 60, 20 * 60 + 30, work=True, assignment="a1", slack="ok", due="2026-11-06T18:00"
    )
    later = _block(
        "Later", 20 * 60, 20 * 60 + 30, work=True, assignment="a2", slack="ok", due="2026-11-06T20:00"
    )
    tags = {row.title: row.tag for row in _board([soon, later], 19 * 60).up_next}
    assert tags["Soon"] == "Tight"
    assert tags["Later"] == "Plenty of time"


def test_an_all_day_due_is_tight_five_hours_before_midnight() -> None:
    soon = _block("Soon", 20 * 60, 20 * 60 + 30, work=True, assignment="a1", slack="ok", due="2026-11-06")
    board = board_for(
        [soon],
        minute=19 * 60,
        when="today",
        nudges=True,
        dim=True,
        mode="light",
        on=date(2026, 11, 6),
        now=datetime(2026, 11, 6, 19, 0),
    )
    assert board.up_next[0].tag == "Tight"


def test_browsing_another_day_takes_its_tags_from_the_clock_not_from_that_day(qapp: QApplication) -> None:
    item = _block(
        "Essay", 2 * 60, 2 * 60 + 30, work=True, assignment="a1", slack="ok", due="2026-11-06T20:00"
    )

    class Window:
        session = SimpleNamespace(
            preferences={},
            account={"id": "review"},
            week_start="2026-11-02",
            selected_day="2026-11-06",
            now_ms=CLOCK.now_ms,
            built_week=lambda: SimpleNamespace(on_day=lambda _: (item,)),
            busy=False,
        )

    parent = QObject()
    bridge = DayBridge(Window(), parent)  # type: ignore[arg-type]
    bridge.reload("light")
    assert bridge._board.up_next[0].tag == "Plenty of time"


def _board_12h(items: list[Occurrence], minute: int):
    set_clock_24h(False)
    try:
        return board_for(items, minute=minute, when="today", nudges=True, dim=True, mode="light", on=TODAY)
    finally:
        set_clock_24h(True)


def test_free_time_says_how_long_then_what_is_next() -> None:
    """Jonathan's words: "Free for 20 min — next: Soccer at 4:00 PM"."""
    essay = _block("History essay", *ESSAY, work=True, assignment="a1")
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER, category="exercise"), essay]
    board = _board_12h(day, 15 * 60 + 40)
    assert board.show_now is True
    assert board.now_title == "Free for 20 min"
    assert board.now_line == "Next: Soccer at 4:00 PM"
    assert "History essay" not in board.now_title + board.now_line
    later = _board_12h(day, 15 * 60 + 47)
    assert later.now_title == "Free for 13 min"
    assert later.now_line == "Next: Soccer at 4:00 PM"
    assert later.ring_count == 2
    longer = _board(day, 13 * 60)
    assert longer.now_title == "Free for 3 h"
    assert longer.now_line == "Next: Soccer at 16:00"


def test_the_start_button_names_the_homework_it_starts() -> None:
    """During free time the card no longer names the homework, so its button does (Jonathan, 2026-11-08)."""
    essay = _block("History essay", *ESSAY, work=True, assignment="a1")
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER, category="exercise"), essay]
    assert _board_12h(day, 15 * 60 + 40).focus_title == "History essay"
    assert _board_12h([_block("School", *SCHOOL)], 15 * 60 + 40).focus_title == ""


def test_free_time_before_a_homework_block_does_not_count_down_the_homework() -> None:
    new = _block("Causes of WW1 essay", 16 * 60, 17 * 60, work=True, assignment="a2")
    board = _board_12h([_block("School", *SCHOOL), new], 15 * 60 + 47)
    assert board.now_title == "Free for 13 min"
    assert board.now_line == "Next: Causes of WW1 essay at 4:00 PM"
    assert board.focus_block_id == "causes-of-ww1-essay"


def test_homework_happening_now_is_named_with_its_time_left() -> None:
    essay = _block("Essay", *ESSAY, work=True, assignment="a1")
    board = _board([_block("School", *SCHOOL), essay], 19 * 60)
    assert board.show_now is True
    assert board.now_title == "Essay"
    assert board.now_line == "45 min left"
    assert board.focus_block_id == "essay"


def test_nothing_left_today_has_no_now_card() -> None:
    essay = _block("Essay", *ESSAY, work=True, assignment="a1", done=True)
    board = _board([_block("School", *SCHOOL), essay], 15 * 60)
    assert board.left_line == "Nothing left today"
    assert board.show_now is False
    assert board.now_title == "" and board.now_line == ""


def test_no_now_card_inside_a_block_after_the_last_one_or_off_today() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER)]
    assert _board(day, 10 * 60).show_now is False
    assert _board(day, 18 * 60).show_now is False
    assert _board(day, 13 * 60, when="future").show_now is False
    assert _board(day, 13 * 60, when="past").show_now is False


def test_a_finished_homework_block_does_not_end_the_gap() -> None:
    done_early = _block("Maths", 14 * 60, 15 * 60, work=True, done=True, assignment="a2")
    day = [done_early, _block("Soccer", *SOCCER)]
    board = _board(day, 14 * 60 + 30)
    assert board.show_now is True
    assert board.now_minutes == 90


def test_nudges_off_hides_the_card() -> None:
    day = [_block("School", *SCHOOL), _block("Soccer", *SOCCER)]
    assert _board(day, 13 * 60, nudges=False).show_now is False


def test_the_nudge_preference_reads_defensively() -> None:
    assert read_flag(None, ("free_time_nudges", "nudges"), True) is True
    assert read_flag({}, ("free_time_nudges", "nudges"), True) is True
    assert read_flag({"free_time_nudges": False}, ("free_time_nudges", "nudges"), True) is False
    assert read_flag({"nudges": False}, ("free_time_nudges", "nudges"), True) is False
    assert read_flag({"free_time_nudges": "no"}, ("free_time_nudges", "nudges"), True) is True


def test_a_4pm_to_530pm_block_is_coming_up_at_340pm_and_done_after_530pm() -> None:
    soccer = _block("Soccer", *SOCCER, category="exercise")
    at_340pm = 15 * 60 + 40
    board_340 = _board([soccer], minute=at_340pm, when="today")
    assert [row.title for row in board_340.up_next] == ["Soccer"]
    assert [row.title for row in board_340.done] == []

    at_535pm = 17 * 60 + 35
    board_535 = _board([soccer], minute=at_535pm, when="today")
    assert [row.title for row in board_535.up_next] == []
    assert [row.title for row in board_535.done] == ["Soccer"]


def test_start_focus_picks_the_next_homework_block() -> None:
    essay = _block("Essay", *ESSAY, work=True, assignment="a1")
    board = _board([_block("Soccer", *SOCCER), essay], 9 * 60)
    assert board.focus_block_id == "essay"
    assert board.focus_day == 3


def test_start_focus_uses_the_material_hook_when_the_window_has_one(qapp: QApplication) -> None:
    heard: list[tuple] = []

    class Window:
        session = SimpleNamespace()

        def start_material_focus(self, block_id: str, day: int) -> None:
            heard.append(("hook", block_id, day))

        def _start_focus(self, block_id: str, day: object) -> None:
            heard.append(("widgets", block_id, day))

    parent = QObject()
    bridge = DayBridge(Window(), parent)  # type: ignore[arg-type]
    bridge._publish(_board([_block("Essay", *ESSAY, work=True, assignment="a1")], 9 * 60))
    bridge.startFocus()
    assert heard == [("hook", "essay", 3)]


def test_start_focus_falls_back_to_the_widgets_start(qapp: QApplication) -> None:
    heard: list[tuple] = []

    class Window:
        session = SimpleNamespace(start_focus=lambda *args: heard.append(("session", args)))

        def _start_focus(self, block_id: str, day: object) -> None:
            heard.append(("widgets", block_id, day))

    parent = QObject()
    bridge = DayBridge(Window(), parent)  # type: ignore[arg-type]
    bridge._publish(_board([_block("Essay", *ESSAY, work=True, assignment="a1")], 9 * 60))
    bridge.startFocus()
    assert heard == [("widgets", "essay", 3)]
