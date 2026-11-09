"""Retro desktop's Notepad: the homework listed under its deadline with its length and time, what has no
time yet shown once, and how a line gives way when the page is short of room."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.layouts.retro import (  # noqa: E402
    NOT_PLACED,
    Deadline,
    deadlines,
    due_heading,
    note_lines,
    note_widths,
    shorten,
)
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402
from desktop.tests.week.support_retro import NBSP, shown, task, text, windows  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-retro-test"])
    yield application


def test_notepad_lists_the_homework_under_its_deadline_with_its_length_and_time(qapp: QApplication) -> None:
    """Chem lab report is due today and placed at 20:00 for 1 h 30; the history essay is due tomorrow at
    21:00 and placed at 18:45 for an hour; the poster, due Sunday at 20:00, has no time yet. Each line's
    length and time sit in columns as wide as the widest. The time a homework is placed at says so, so
    it is never read as when it is due, which the heading above it says."""
    view = shown(qapp)
    headings = [label.text() for label in view.findChildren(QLabel, "retroNoteDue")]
    assert headings == [
        "Due Thursday 17 September, today.",
        "Due Friday 18 September at 21:00, tomorrow.",
        f"Due Sunday 20 September at 20:00, in{NBSP}3{NBSP}days.",
    ]
    rows = [view.findChild(QPushButton, name) for name in ("retroNote0", "retroNote1", "retroNoteWaiting0")]
    assert [row.lines for row in rows] == [
        ["Chem-1    1h 30m  placed Thu 20:00"],
        ["Essay-1   1h      placed Thu 18:45"],
        [f"Poster-1  2h      {NOT_PLACED}"],
    ]
    chip = view.findChild(TrayChip, "retroNoteWaiting0")
    assert chip.block_id == "poster-1"
    assert chip.hand is view.hand
    assert text(view, "retroNotesHint") == f"1 {NOT_PLACED}: drag it onto Week.exe, or use Plan my homework."
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    rows[0].click()
    assert opened == ["chem-1"]


def test_what_has_no_time_is_shown_once_in_the_notepad_or_under_the_hours_when_it_is_closed(
    qapp: QApplication,
) -> None:
    view = shown(qapp)

    def seen() -> list[str]:
        # A closed window is kept, hidden, with its chip in it: out of sight, out of the mouse's and
        # Tab's reach. A chip made as a click is handled shows once the event loop runs again.
        qapp.processEvents()
        chips = view.findChildren(TrayChip)
        return [chip.objectName() for chip in chips if chip.block_id == "poster-1" and chip.isVisible()]

    assert seen() == ["retroNoteWaiting0"]
    QTest.mouseClick(view.findChild(QPushButton, "retroClose-notes"), Qt.MouseButton.LeftButton)
    assert seen() == ["retroWaiting0"]
    QTest.mouseClick(task(view, "notes"), Qt.MouseButton.LeftButton)
    assert seen() == ["retroNoteWaiting0"]


def test_closing_the_notepad_cannot_hide_what_has_no_time(qapp: QApplication) -> None:
    view = shown(qapp, windows="week")
    assert windows(view) == ["retroWindow-week"]
    waiting = view.findChild(TrayChip, "retroWaiting0")
    assert waiting.text() == "Poster-1 · 2 h"
    assert waiting.hand is view.hand
    assert "There isn't enough time left before it's due" in waiting.toolTip()


def test_a_notepad_line_short_of_room_puts_its_length_and_time_under_its_title(qapp: QApplication) -> None:
    """At 1150x768 with large text a long title leaves no room on its line for the length and time,
    so they go on the line under it, whole; the title is shortened only at a word."""
    long = [
        item if item["id"] != "essay-1" else {**item, "title": "History essay on the causes of the war"}
        for item in BLOCKS
    ]
    view = shown(qapp, 1150, 768, blocks=long, scale=1.4)
    qapp.processEvents()
    essay = next(row for row in view.findChildren(QPushButton) if row.objectName() == "retroNote1")
    assert len(essay.lines) == 2, essay.lines
    assert "History essay on the causes of the war".startswith(essay.lines[0].removesuffix("…"))
    # Under the title, in from the edge; "placed" leaves this narrow page no title column.
    assert essay.lines[1].split() == ["1h", "placed", "Thu", "18:45"] and essay.lines[1].startswith("  ")


def test_notepads_columns_and_their_fallbacks() -> None:
    chem = Deadline("Chem lab report", "1 h 30", "Mon 20:00", "chem-1")
    spanish = Deadline("Spanish vocab", "30 min", NOT_PLACED, "spanish-1")
    assert note_widths([chem, spanish], 42) == (15, 6)
    # On a narrower page the title column gives way to the lengths and times.
    assert note_widths([chem, spanish], 30) == (6, 6)
    assert note_lines(chem, (15, 6), 42) == ["Chem lab report  1 h 30  Mon 20:00"]
    assert note_lines(spanish, (15, 6), 42) == ["Spanish vocab    30 min  not placed yet"]
    # Too narrow for the columns beside the title: they go under it, in from the edge.
    assert note_lines(chem, (15, 6), 30) == ["Chem lab report", "   1 h 30  Mon 20:00"]
    # A title wider than its column, on a page wide enough for the columns: under it, in their columns.
    assert note_lines(chem, (10, 6), 42) == ["Chem lab report", "            1 h 30  Mon 20:00"]
    assert shorten("History essay on the causes of the war", 30) == "History essay on the causes…"
    assert shorten("Supercalifragilistic", 8) == "Superca…"


def test_a_notepad_title_that_is_cut_still_shows_its_start() -> None:
    """A title cut to fit the page keeps its length and the day and time it is placed (its start) on
    the line under it, or "not placed yet" for homework that has none."""
    placed = Deadline("History essay on the causes of the war", "2 h", "Mon 20:00", "history-1")
    waiting = Deadline("Mathematics worksheet on fractions and ratios", "45 min", NOT_PLACED, "math-1")
    chars = 30
    widths = note_widths([placed, waiting], chars)
    for line, start in ((placed, "Mon 20:00"), (waiting, NOT_PLACED)):
        said = note_lines(line, widths, chars)
        assert len(said) == 2, said
        assert said[0].endswith("…") and len(said[0]) <= chars, said
        assert said[1].endswith(start) and len(said[1]) <= chars, said
        assert line.length in said[1], said


def test_a_deadline_says_when_it_is_from_today() -> None:
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    assert due_heading("2026-09-17T23:59", week, 3) == "Due Thursday 17 September, today."
    assert due_heading("2026-09-18T21:00", week, 3) == "Due Friday 18 September at 21:00, tomorrow."
    assert due_heading("2026-09-15T08:00", week, 3) == "Due Tuesday 15 September at 08:00, past due."
    assert due_heading("2026-09-20T23:59", week, None) == "Due Sunday 20 September."
    assert due_heading(None, week, 3) == "No due date."
    groups = deadlines(week, 3)
    assert [[line.block_id for line in group.lines] for group in groups] == [
        ["chem-1"],
        ["essay-1"],
        ["poster-1"],
    ]
