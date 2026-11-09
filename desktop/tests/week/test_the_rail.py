"""Today's app's rail: what is next, Not placed yet and the focus list left of Day and Week, the
running timer as its first card, the mini month folded away and remembered, the one-go message, and
the window's floor. How the rail looks (widths, gaps, fit) is in pictures/week_material.py."""

# ruff: noqa: F811
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAccessible, QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QLabel, QPushButton, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.hours.rail import focus_when, rail_title_lines
from desktop.native.look import sanitize_look
from desktop.native.weekmodel import due_label
from desktop.native.window import WINDOW_MIN_WIDTH, NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import chips, pump, seeded, use_clock
from desktop.tests.window_support import look_file, qapp, settled  # noqa: F401


def test_the_rail_holds_next_not_placed_yet_and_the_focus_list_left_of_the_week(qapp, window) -> None:
    """The side panel went; a slim rail left of the hours holds what it held. Above the hours there is
    only the top bar."""
    seeded(qapp, window)
    rail = window.rail
    assert window.planner.currentWidget() is window.week_table
    assert rail.isVisible() and not rail.folded
    assert not rail.month.isVisible()
    card = rail.next
    assert card.isVisible()
    assert (card.label.text(), card.title.text(), card.when.text(), card.then.text()) == (
        "Next",
        "Soccer practice",
        "4:00 PM · in 20 min",
        "Then Dinner at 6:30 PM",
    )
    assert window.findChild(QWidget, "weekStatusStrip") is None
    # In time order with the time at the right, today's said as Today.
    assert rail.task_rows() == [("History essay", "Today 7:00 PM")]
    assert [chip.accessibleName() for chip in chips(window)] == ["Math worksheet · 1 h"]
    assert rail.waiting_count.text() == "1"
    use_clock(qapp, window, True)
    assert (card.when.text(), card.then.text()) == ("16:00 · in 20 min", "Then Dinner at 18:30")
    assert rail.task_rows() == [("History essay", "Today 19:00")]
    use_clock(qapp, window, False)
    assert not window.focus_panel.isVisible()
    # Day keeps the rail, and says what is next there instead of in a band above its hours.
    window.findChild(QAbstractButton, "viewDay").click()
    wait_until(qapp, lambda: window.planner.currentWidget() is window.day_view)
    qapp.processEvents()
    assert rail.isVisible() and card.isVisible()
    assert not window.focus_panel.now_next.isVisible(), "Day's Next band is gone"


def test_the_focus_list_is_in_time_order_with_undated_rows_last(qapp, window) -> None:
    """A plan can leave the tasks out of order; the list reads by day, then by start."""
    seeded(qapp, window)
    rows = [
        {"id": "late", "day": 4, "start": "17:00", "title": "Friday late"},
        {"id": "undated", "title": "No day"},
        {"id": "early", "day": 1, "start": "09:00", "title": "Tuesday early"},
        {"id": "first", "day": 4, "start": "08:00", "title": "Friday early"},
    ]
    window.rail.set_tasks(rows, 3)
    assert [title for title, _when in window.rail.task_rows()] == [
        "Tuesday early",
        "Friday early",
        "Friday late",
        "No day",
    ]


def test_a_focus_row_says_the_day_and_start(qapp) -> None:
    assert focus_when({"day": 0, "start": "06:00"}, today=3) == "Mon 06:00"


def test_the_month_opens_from_the_week_title_and_picking_a_date_goes_to_its_week(qapp, window) -> None:
    seeded(qapp, window)
    week = date.fromisoformat(window.session.week_start)
    assert not window.rail.month.isVisible()
    QTest.mouseClick(window.week_title, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    month = window.month_pick
    assert window.month_pop.isVisible() and month.dates.week_start == week.isoformat()
    assert sunday_due(window.session.week_start)[:10] in month.dates.due, "a dot on the day homework is due"
    shown = [day.isoformat() for day in month.dates.dates()]
    # The month shown is the one holding this week; two weeks on can fall past its last row
    # (the week of 19 Oct 2026 is one), so the test then goes two weeks back instead.
    later = week + timedelta(days=14)
    if later.isoformat() not in shown:
        later = week - timedelta(days=14)
    assert later.isoformat() in shown, "a week two weeks away is on the month shown"
    QTest.mouseClick(
        month.dates,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        month.dates.date_point(later.isoformat()).toPoint(),
    )
    wait_until(qapp, lambda: window.session.week_start == later.isoformat() and not window.session.busy)
    assert not window.month_pop.isVisible()


def test_the_month_folded_from_its_header_is_still_folded_after_a_restart(qapp, window) -> None:
    seeded(qapp, window)
    rail = window.rail
    assert rail.month_shown
    rail.month.fold.click()
    assert not rail.month_shown
    kept = json.loads(look_file().read_text())
    assert kept["rail"] == {"month": False}
    # A restart reads the look file again; shown first, so only the file can fold it.
    rail.set_month_shown(True)
    assert rail.month_shown
    window._load_look()
    assert not rail.month_shown


def test_the_mini_month_names_its_week_in_the_apps_date_order(qapp, window) -> None:
    seeded(qapp, window)
    window.rail.month.show_week("2026-10-05", date(2026, 10, 7), frozenset())
    assert window.rail.month.dates.accessibleDescription() == "Shows the week of Mon 5 Oct."


def test_a_running_timer_is_the_rails_first_card(qapp, window) -> None:
    """Decision 15: the timer is the rail's first card, not a strip over the hours."""
    seeded(qapp, window)
    essay = next(block for block in window.session.blocks if block.get("assignment_id") == "essay")
    window.session.start_focus(essay["id"], 3)
    wait_until(qapp, lambda: window.session.focus is not None)
    window._on_week()
    qapp.processEvents()
    panel, rail = window.focus_panel, window.rail
    assert panel.isVisible() and rail.isAncestorOf(panel)
    tops = {
        name: widget.mapTo(rail, QPoint(0, 0)).y() for name, widget in (("timer", panel), ("next", rail.next))
    }
    assert tops["timer"] < tops["next"], tops
    assert not rail.month.isVisible()
    # Today's app shows the one-line strip the other designs show, not the homework's name.
    assert panel.task.text() == "History essay · 30:00 left"
    window.session.reset_focus()
    wait_until(qapp, lambda: window.session.focus is None)


def test_the_compact_focus_line_is_shortened_but_still_read_out_whole_at_large_text(qapp, window) -> None:
    seeded(qapp, window)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window._apply_appearance()
    essay = next(block for block in window.session.blocks if block.get("assignment_id") == "essay")
    window.session.start_focus(essay["id"], 3)
    wait_until(qapp, lambda: window.session.focus is not None)
    window.session.focus["title"] = "History essay draft"
    window._on_week()
    qapp.processEvents()
    panel = window.focus_panel
    assert panel.isVisible() and panel._compact and panel.task.isVisible()
    assert panel.task.text().endswith(" left")
    assert "30:00" in panel.task.text()
    # The full name and time are still read out.
    spoken = QAccessible.queryAccessibleInterface(panel.task).text(QAccessible.Text.Name)
    assert "History essay draft" in spoken and "30:00 left" in spoken
    window.session.reset_focus()
    wait_until(qapp, lambda: window.session.focus is None)


def test_high_contrast_keeps_chip_names_to_two_lines_and_the_focus_list_off_the_rail(qapp, window) -> None:
    """Switched to High contrast with the rail up, its larger text ran the chips' words off their edge
    and gave the focus list a sideways scroll bar and a row short."""
    seeded(qapp, window)
    session = window.session
    session.add_homework(
        {
            "id": "poster",
            "title": "Science poster for the fair",
            "due": sunday_due(session.week_start),
            "estimate_min": 90,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    window._look = sanitize_look({"preset": "high-contrast", "knobs": {}})
    window._apply_appearance()
    pump(qapp)
    rail = window.rail
    shown = chips(window)
    assert len(shown) == 2
    for chip in shown:
        assert len(chip.title_lines()) <= 2
    assert not rail.focus.isVisible()
    assert not rail.scroll.horizontalScrollBar().isVisible()
    starts = [button for button in rail.next.findChildren(QPushButton) if button.text() == "Start focus"]
    assert starts


def test_a_narrow_window_keeps_the_rail_whole_and_blocks_keep_their_times(qapp, window) -> None:
    seeded(qapp, window)
    rail, hours = window.rail, window.week_table
    window.resize(1100, 860)
    pump(qapp)
    assert not rail.folded and not hours.hours.short_words
    assert rail.next.isVisible() and not rail.month.isVisible()
    assert rail.waiting_label.text() == "No time yet · drag onto a day"
    chip = rail.chips()[0]
    assert chip.isVisible()
    window.resize(1280, 860)
    pump(qapp)
    assert not rail.folded and not hours.hours.short_words
    assert chip.isVisible()


def test_the_window_is_never_narrower_than_800(qapp, window) -> None:
    assert WINDOW_MIN_WIDTH == 800
    window.resize(650, 720)
    pump(qapp, 3)
    assert window.width() == 800


def test_the_next_card_after_the_last_class_offers_start_focus(qapp, window) -> None:
    seeded(qapp, window)
    session = window.session
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(hours=19))
    session.week_changed.emit()
    settled(qapp, window)
    math = next(block for block in session.blocks if block.get("assignment_id") == "math")
    session.add_block({**math, "start": "17:00", "days": [4], "pinned": True})
    session.save()
    settled(qapp, window)
    pump(qapp)
    assert window.rail.next.title.text() == "Chem lab report"
    assert window.rail.next.start_focus.isVisible()
    assert window.rail.next.start_focus.text() == "Start focus"


def test_the_focus_list_is_as_tall_as_all_its_rows_so_no_row_is_cut(qapp, window) -> None:
    """The list was a small scrolling box that clipped the last row ("Fri 17:0(")."""
    seeded(qapp, window)
    rows = [{"id": f"t{n}", "day": 4, "start": "17:00", "title": f"Task {n}"} for n in range(3)]
    window.rail.set_tasks(rows, 0)
    qapp.processEvents()
    tasks = window.rail.tasks
    assert tasks.count() == 3
    needed = sum(tasks.item(row).sizeHint().height() for row in range(tasks.count()))
    assert tasks.height() >= needed, (tasks.height(), needed)


def test_the_focus_list_has_no_row_limit_and_no_scroll_bar_of_its_own(qapp, window) -> None:
    """The rail scrolls as a whole, so the list never needs a scroll bar of its own."""
    seeded(qapp, window)
    rows = [{"id": f"t{n}", "day": 4, "start": "17:00", "title": f"Task {n}"} for n in range(9)]
    window.rail.set_tasks(rows, 0)
    qapp.processEvents()
    assert window.rail.tasks.count() == 9
    assert not window.rail.focus.isVisible()
    assert not window.rail.scroll.horizontalScrollBar().isVisible()


@pytest.mark.parametrize("twenty_four", [True, False])
def test_rail_chips_and_focus_rows_wrap_long_names_on_two_lines_at_large_text(
    qapp, window, twenty_four: bool
) -> None:
    """#84: "Math worksheet, chapter 4" and "History / essay" stay whole on two lines, not "Math worksh…".
    On the 12-hour clock the time ("Today 7:00 PM") is wider and left too little room for "worksheet,"."""
    seeded(qapp, window)
    use_clock(qapp, window, twenty_four)
    session = window.session
    due = sunday_due(session.week_start)
    for key, title in (
        ("long-math", "Math worksheet, chapter 4"),
        ("long-history", "History / essay"),
    ):
        session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window._apply_appearance()
    pump(qapp)
    by_title = {chip._title: chip for chip in window.rail.chips()}
    for title in ("Math worksheet, chapter 4", "History / essay"):
        chip = by_title[title]
        lines = chip.title_lines()
        assert len(lines) <= 2
        assert " ".join(lines) == title
        assert "…" not in chip.shown_title()
        assert title in chip.accessibleName()
        body, _small = chip._fonts()
        assert rail_title_lines(title, QFontMetricsF(body), chip._title_room()) == lines
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.add_block({**essay, "start": "18:00", "days": [3], "pinned": True})
    math = next(block for block in session.blocks if block.get("assignment_id") == "long-math")
    session.add_block({**math, "start": "19:00", "days": [3], "pinned": True})
    history = next(block for block in session.blocks if block.get("assignment_id") == "long-history")
    session.add_block({**history, "start": "20:00", "days": [3], "pinned": True})
    session.save()
    settled(qapp, window)
    pump(qapp)
    # Homework Start focus lives on Next rows now; the long names stay whole on the chips above.
    for width in (1157, 1280):
        window.resize(width, 800)
        pump(qapp)
        titles = [label.text() for label in window.rail.next.rest.findChildren(QLabel, "railNextRowTitle")]
        assert "Math worksheet, chapter 4" in titles
        assert "History / essay" in titles
        assert all("…" not in title for title in titles)


def _one_go(window: NativeWindow) -> str:
    """Gives the rail one homework that does not fit in one go; returns the due it was given."""
    due = sunday_due(window.session.week_start)
    window.rail.set_week(
        window.rail._week,
        window.rail._today,
        window.rail._minute,
        {"chemistry": {"title": "Long chemistry report", "due": due}},
        [{"assignment_id": "chemistry", "title": "Long chemistry report", "minutes": 2400}],
        {"chemistry"},
    )
    return due


def test_the_rail_says_a_task_does_not_fit_in_one_go_and_offers_to_split_it(qapp, window) -> None:
    seeded(qapp, window)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window._apply_appearance()
    due = _one_go(window)
    qapp.processEvents()
    message = window.rail.findChild(QLabel, "railOneGoMessage")
    action = window.rail.findChild(QPushButton, "railAllowSplitting")
    assert message is not None, "the one-go message is present"
    assert action is not None, "the one-go action is present"
    assert message.wordWrap(), "the one-go message wraps instead of overflowing the rail"
    assert action.accessibleName() == (
        f"Long chemistry report doesn't fit in one go before {due_label(due, window.session.week_start)}. "
        "Allow splitting?"
    ), "the one-go action retains the task and due date"


@pytest.mark.parametrize(
    ("twenty_four", "words"), [(True, "18:45 · Starting now"), (False, "6:45 PM · Starting now")]
)
def test_the_ringing_alarm_says_its_time_on_the_clock_the_student_chose(
    qapp, window, twenty_four: bool, words: str
) -> None:
    from desktop.native.settings import AlarmRingDialog

    use_clock(qapp, window, twenty_four)
    dialog = AlarmRingDialog(window, {"name": "Guitar practice", "time": "18:45", "block": "guitar"}, "")
    assert dialog.findChild(QLabel, "alarmDetail").text() == words
