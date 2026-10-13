"""The count on More is the one count (0.19.2, P1 rule d and guard 6).

The Unfinished badge, More's Unfinished row, its panel and the rail's Not placed yet all read the
engine's time-still-needed list. The count is a pill painted over More's corner: it never adds a bar
above the week, and never changes the size the top bar sees.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import contrast, count_pill, resolved_palette
from desktop.native.weekmodel import length_label
from desktop.native.window import NativeWindow
from desktop.tests.window_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_out,
    wait_until,
    window,
)


def due_in(window: NativeWindow, days: int) -> str:  # noqa: F811
    return (date.fromisoformat(window.session.week_start) + timedelta(days=days)).isoformat() + "T23:59"


def add(window: NativeWindow, key: str, title: str, minutes: int, due: str) -> None:  # noqa: F811
    window.session.add_homework(
        {"id": key, "title": title, "estimate_min": minutes, "revision": 0, "due": due}
    )


def more_row(window: NativeWindow) -> tuple[bool, str]:  # noqa: F811
    window._sync_more_menu()
    for action, button in window._more_pairs:
        if button.objectName() == "unfinishedOpen":
            return action.isEnabled(), action.text()
    raise AssertionError("More has no Unfinished row")


def panel_rows(window: NativeWindow) -> list[str]:  # noqa: F811
    panel = window.unfinished_panel
    return [
        label.text()
        for label in panel.findChildren(QLabel)
        if label.objectName() == "unfinishedRow" and label.isVisibleTo(window)
    ]


def left_over_week_two(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """An essay due three days ago with its time deleted, seen from the week after: homework from an
    earlier week. Then work due that week, and work due the week after, neither placed."""
    session = window.session
    week = date.fromisoformat(session.week_start)
    session.add_block({"id": "school", "title": "School", "kind": "locked", "start": "08:00",
                       "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    add(window, "essay", "History essay", 120, (date.today() - timedelta(days=3)).isoformat() + "T12:00")
    session.save()
    settled(qapp, window)
    planned = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.delete_block(planned["id"])
    session.save()
    settled(qapp, window)
    later = (week + timedelta(days=7)).isoformat()
    session.load_week(later)
    wait_until(qapp, lambda: session.week_start == later and not session.busy)
    add(window, "math", "Math worksheet", 60, due_in(window, 4))
    add(window, "lab", "Chem lab", 90, due_in(window, 10))
    session.save()
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()


def test_badge_more_row_panel_and_rail_show_the_same_items_and_minutes(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """Guard 6: earlier-week, this-week and later work, one list in four places."""
    left_over_week_two(qapp, window)
    needed = window.session.homework_time_needed()
    assert {item["assignment_id"] for item in needed} == {"essay", "math", "lab"}
    minutes = {item["title"]: item["minutes"] for item in needed}
    assert minutes == {"History essay": 120, "Math worksheet": 60, "Chem lab": 90}
    lines = sorted(f"{title} · {length_label(amount)} left" for title, amount in minutes.items())
    assert window.more_button.accessibleName() == "More, 3 homework still need time"
    enabled, row = more_row(window)
    assert enabled and row == "Unfinished\t3 left"
    assert window.rail.waiting_count.text() == "3"
    assert sorted(window.rail.none_waiting.text().split("\n")) == lines
    window.findChild(QPushButton, "unfinishedOpen").click()
    qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window)
    essay_due = date.today() - timedelta(days=3)
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


def test_work_due_this_week_with_a_chip_is_counted(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    add(window, "math", "Math worksheet", 60, due_in(window, 6))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    assert [item["assignment_id"] for item in window.session.homework_time_needed()] == ["math"]
    assert window.rail.waiting_count.text() == "1"
    assert window.more_button.accessibleName() == "More, 1 homework still needs time"
    assert more_row(window) == (True, "Unfinished\t1 left")


def test_the_count_goes_up_and_down_and_nothing_moves(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
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
    for _ in range(5):
        qapp.processEvents()
    assert window.session.homework_time_needed() == []

    def geometry() -> tuple[int, ...]:
        more = window.more_button
        return (
            window.planner.mapTo(window, QPoint(0, 0)).y(),
            window._top_bar.geometry().height(),
            window.more_button.geometry().height(),
            more.sizeHint().width(),
            more.sizeHint().height(),
        )

    before = geometry()
    assert window.more_button.accessibleName() == "More"
    add(window, "history", "History", 120, due_in(window, 9))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.more_button.accessibleName() == "More, 1 homework still needs time"
    assert geometry() == before
    add(window, "bio", "Bio", 60, due_in(window, 5))
    window.session.save()
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.more_button.accessibleName() == "More, 2 homework still need time"
    assert geometry() == before
    for key in ("history", "bio"):
        settled(qapp, window)
        assert window.session.delete_homework(key)
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.session.homework_time_needed() == []
    assert window.more_button.accessibleName() == "More"
    assert geometry() == before
    assert more_row(window) == (False, "Unfinished\tNone left")


def test_there_is_no_bar_above_the_week_for_the_count(window: NativeWindow) -> None:  # noqa: F811
    assert window.findChild(QPushButton, "unfinishedBadge") is None
    assert not hasattr(window, "unfinished_badge")
    assert not hasattr(window.session, "homework_time_needed_elsewhere")


def test_unfinished_opens_a_panel_with_exactly_the_counted_titles(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
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


def test_a_greyed_unfinished_opens_nothing(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window.session.save()
    settled(qapp, window)
    window._on_week()
    assert more_row(window) == (False, "Unfinished\tNone left")
    window._show_unfinished()
    assert not window.unfinished_panel.isVisibleTo(window)


@pytest.mark.parametrize(
    ("pack", "dark", "look"),
    [
        ("light-frost", False, None),
        ("dark-frost", True, None),
        ("system", False, {"preset": "high-contrast", "knobs": {}}),
        ("system", True, {"preset": "paper", "knobs": {}}),
        ("slate", False, {"preset": "terminal", "knobs": {}}),
    ],
)
def test_the_count_pill_reads_three_to_one_on_the_bar_and_its_words_four_and_a_half(
    pack: str, dark: bool, look: dict | None
) -> None:
    palette = resolved_palette(pack, dark, look or {"preset": "default", "knobs": {}})
    fill, ink = count_pill(palette)
    assert contrast(fill, palette["window"]) >= 3.0
    assert contrast(ink, fill) >= 4.5
