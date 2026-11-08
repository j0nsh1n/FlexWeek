"""The count on More is the one count (P1 rule d and guard 6).

The Unfinished badge, More's Unfinished row, its panel and the rail's Not placed yet all read the
engine's time-still-needed list. The count is a pill painted over More's corner: it never adds a bar
above the week. That the pill never changes the size the top bar sees, and how it reads on the bar, are
the pictures settings.more_count_none, settings.more_count_two and settings.more_count_pill.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from backend.tests.fake_clock import CLOCK
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.weekmodel import length_label
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_more import (
    add,
    due_in,
    left_over_week_two,
    more_row,
    overdue_this_week,
    panel_rows,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_badge_more_row_panel_and_rail_show_the_same_items_and_minutes(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Guard 6: earlier-week, this-week and later work, one list in four places."""
    left_over_week_two(qapp, window)
    needed = window.session.homework_time_needed()
    assert {item["assignment_id"] for item in needed} == {"essay", "math", "lab"}
    minutes = {item["title"]: item["minutes"] for item in needed}
    assert minutes == {"History essay": 120, "Math worksheet": 60, "Chem lab": 90}
    lines = sorted(f"{title} · {length_label(amount)} left" for title, amount in minutes.items())
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework, 3 homework still need time"
    enabled, row = more_row(window)
    assert enabled and row == "Unfinished\t3 left"
    assert window.rail.waiting_count.text() == "3"
    assert sorted(window.rail.none_waiting.text().split("\n")) == lines
    window.findChild(QPushButton, "unfinishedOpen").click()
    qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window)
    essay_due = CLOCK.today() - timedelta(days=3)
    due_words = f"due {essay_due.strftime('%a')} {essay_due.day} {essay_due.strftime('%b')}"
    panel_lines = sorted(
        (
            f"{title} · {length_label(amount)} left · {due_words} · Overdue"
            if title == "History essay"
            else f"{title} · {length_label(amount)} left"
        )
        for title, amount in minutes.items()
    )
    assert sorted(panel_rows(window)) == panel_lines
    assert window.unfinished_panel.findChild(QPushButton, "planUnfinished-essay") is not None


def test_work_due_this_week_with_a_chip_is_counted(qapp: QApplication, window: NativeWindow) -> None:
    add(window, "math", "Math worksheet", 60, due_in(window, 6))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    assert [item["assignment_id"] for item in window.session.homework_time_needed()] == ["math"]
    assert window.rail.waiting_count.text() == "1"
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework, 1 homework still needs time"
    assert more_row(window) == (True, "Unfinished\t1 left")


def test_the_count_goes_up_and_down_with_the_homework_that_needs_a_time(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    window.session.set_view("week")
    window.resize(1280, 860)
    window.show()
    # An empty week shows its own page without the rail; the first thing on it is not the count's doing.
    window.session.add_block({"id": "school", "title": "School", "kind": "locked", "start": "08:00",
                              "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    window.session.save()
    settled(qapp, window)
    window._on_week()
    wait_until(qapp, lambda: window.planner.currentWidget() is window.week_table)
    assert window.session.homework_time_needed() == []
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework"
    add(window, "history", "History", 120, due_in(window, 9))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework, 1 homework still needs time"
    add(window, "bio", "Bio", 60, due_in(window, 5))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework, 2 homework still need time"
    for key in ("history", "bio"):
        settled(qapp, window)
        assert window.session.delete_homework(key)
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.session.homework_time_needed() == []
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName() == "Plan my homework"
    assert more_row(window) == (False, "Unfinished\tNone left")


def test_there_is_no_bar_above_the_week_for_the_count(window: NativeWindow) -> None:
    assert window.findChild(QPushButton, "unfinishedBadge") is None
    assert not hasattr(window, "unfinished_badge")
    assert not hasattr(window.session, "homework_time_needed_elsewhere")


def test_unfinished_opens_a_panel_with_exactly_the_counted_titles(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Work due this week and work due later are not overdue and not from an earlier week: the panel
    lists them too, and Plan stays on the rows that can still be planned."""
    add(window, "math", "Math worksheet", 60, due_in(window, 6))
    add(window, "lab", "Chem lab", 90, due_in(window, 10))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    counted = {item["title"] for item in window.session.homework_time_needed()}
    assert counted == {"Math worksheet", "Chem lab"}
    assert not window.unfinished_panel.isVisibleTo(window)
    window.findChild(QPushButton, "unfinishedOpen").click()
    qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window)
    assert {row.rpartition(" · ")[0] for row in panel_rows(window)} == counted
    for key in ("math", "lab"):
        has_plan = window.unfinished_panel.findChild(QPushButton, f"planUnfinished-{key}") is not None
        assert has_plan == (window.session.remaining_for(key) >= 15), key
        assert window.unfinished_panel.findChild(QPushButton, f"deleteUnfinished-{key}") is not None
    window._on_week()
    qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window), "a change to the week closed the list"
    assert {row.rpartition(" · ")[0] for row in panel_rows(window)} == counted


def test_a_greyed_unfinished_opens_nothing(qapp: QApplication, window: NativeWindow) -> None:
    window.session.save()
    settled(qapp, window)
    window._on_week()
    assert more_row(window) == (False, "Unfinished\tNone left")
    window._show_unfinished()
    assert not window.unfinished_panel.isVisibleTo(window)


def test_more_counts_only_panel_rows_that_need_a_time(qapp: QApplication, window: NativeWindow) -> None:
    overdue_this_week(qapp, window)
    add(window, "art", "Art", 30, due_in(window, 6))
    window.session.save()
    settled(qapp, window)
    assert more_row(window) == (True, "Unfinished\t1 left")
    window._show_unfinished()
    settled(qapp, window)
    assert window.unfinished_panel.list.count() == 2
    assert {item["assignment_id"] for item in window.session.homework_time_needed()} == {"art"}
    buttons = [
        window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(index)).findChild(
            QPushButton, "focusUnfinished-bio"
        )
        for index in range(window.unfinished_panel.list.count())
    ]
    assert any(button is not None for button in buttons)
