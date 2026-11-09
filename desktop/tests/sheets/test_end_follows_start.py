"""Changing Start in the block editor moves End along only once Start is settled, never while it is half
typed; End stops following once it was typed by hand, and is held at 24:00 instead of wrapping to the
morning. School hours carries no length, so there Start never moves End. Keys go through the window
system's path."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import QLabel, QWidget

from desktop.native.weekmodel import clock_text
from desktop.native.widgets import BlockDialog, SchoolHoursDialog
from desktop.tests.sheets.support_fixed_time import go_when
from desktop.tests.sheets.support_keys import hhmm, press, tab_in, type_text, up
from desktop.tests.window_support import free, qapp  # noqa: F401


@pytest.fixture()
def editor(qapp):
    host = QWidget()
    made: list[QWidget] = []

    def open_editor(start: str = "16:00", minutes: int = 60) -> BlockDialog:
        dialog = up(qapp, BlockDialog(host, day=3, start=start, duration_min=minutes))
        dialog.title.setText("Club")
        go_when(dialog)
        made.append(dialog)
        return dialog

    yield open_editor
    for widget in made:
        widget.hide()
        free(widget)
    free(host)


def test_end_does_not_move_while_start_is_half_typed(editor) -> None:
    dialog = editor()
    ends = []
    tab_in(dialog.start)
    for char in "18:00":
        type_text(dialog.start, char)
        ends.append(hhmm(dialog.end))
    assert ends == ["17:00"] * 5, f"End while typing Start: {ends}"


def test_end_follows_a_settled_start(editor) -> None:
    dialog = editor()
    tab_in(dialog.start)
    type_text(dialog.start, "18:00")
    press(dialog.start, Qt.Key.Key_Tab)
    assert (hhmm(dialog.start), hhmm(dialog.end)) == ("18:00", "19:00")
    dialog.accept()
    assert dialog.block()["duration_min"] == 60


def test_start_never_moves_an_end_typed_by_hand(editor) -> None:
    dialog = editor()
    tab_in(dialog.end)
    type_text(dialog.end, "17:30")
    press(dialog.end, Qt.Key.Key_Tab)
    assert hhmm(dialog.end) == "17:30"
    tab_in(dialog.start)
    type_text(dialog.start, "15:00")
    press(dialog.start, Qt.Key.Key_Tab)
    assert (hhmm(dialog.start), hhmm(dialog.end)) == ("15:00", "17:30")


def test_end_is_held_at_midnight_with_a_message(editor) -> None:
    """Start 16:00 to 23:30 on a 90 min block: End is 24:00 with a message, not 01:00."""
    dialog = editor(minutes=90)
    dialog.start.setTime(QTime(23, 30))
    assert dialog.end.minutes() == 24 * 60, f"End is {hhmm(dialog.end)}"
    said = [label.text() for label in dialog.findChildren(QLabel) if label.isVisible()]
    assert any("24:00" in text or "midnight" in text.lower() for text in said), said


def test_a_moved_end_keeps_the_blocks_length_for_the_next_start(editor) -> None:
    """Held at 24:00, End is 30 min after Start but the block is still 90 min: Start back to 22:00 puts End
    at 23:30, not 22:30."""
    dialog = editor(minutes=90)
    dialog.start.setTime(QTime(23, 30))
    assert hhmm(dialog.end) == "24:00"
    dialog.start.setTime(QTime(22, 0))
    assert hhmm(dialog.end) == "23:30"


def test_the_duration_line_says_end_moved(editor) -> None:
    dialog = editor()
    tab_in(dialog.start)
    type_text(dialog.start, "16:30")
    press(dialog.start, Qt.Key.Key_Tab)
    assert dialog.duration_line.text() == f"End moved to {clock_text(17 * 60 + 30)} to keep it 1 h."


def test_a_start_after_a_typed_end_says_end_needs_to_be_later(editor) -> None:
    dialog = editor()
    tab_in(dialog.end)
    type_text(dialog.end, "17:00")
    press(dialog.end, Qt.Key.Key_Tab)
    tab_in(dialog.start)
    type_text(dialog.start, "18:00")
    press(dialog.start, Qt.Key.Key_Tab)
    assert hhmm(dialog.end) == "17:00"
    assert dialog.duration_line.text() == "End needs to be later than Start (18:00)."


def test_end_moved_is_announced_once_politely(editor, monkeypatch) -> None:
    said: list[tuple[str, bool]] = []

    def record(widget, text, assertive=False) -> None:
        said.append((text, assertive))

    monkeypatch.setattr("desktop.native.widgets.announce", record)
    dialog = editor()
    dialog.start.setTime(QTime(16, 30))
    assert said == [("End moved to 17:30 to keep it 1 h.", False)]


def test_school_hours_start_never_moves_end(qapp) -> None:
    host = QWidget()
    dialog = up(qapp, SchoolHoursDialog(host))
    try:
        before = hhmm(dialog.times.end)
        tab_in(dialog.times.start)
        type_text(dialog.times.start, "09:15")
        press(dialog.times.start, Qt.Key.Key_Tab)
        assert (hhmm(dialog.times.start), hhmm(dialog.times.end)) == ("09:15", before)
    finally:
        dialog.hide()
        free(dialog)
        free(host)
