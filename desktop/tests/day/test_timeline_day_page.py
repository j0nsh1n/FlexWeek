"""Timeline's Day: one page of hours for the whole day on the left, its notes on the facing page, with
the day summed up, what is next and what is due this week."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.geometry import Axis  # noqa: E402
from desktop.native.widgets import use_app_style  # noqa: E402
from desktop.tests.week.support_timeline import (  # noqa: E402
    THURSDAY,
    canvas,
    drawn_words,
    plain,
    scroll_of,
    shown,
    texts,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-timeline-test"])
    use_app_style(application)
    yield application


def test_day_is_one_column_of_the_whole_day_on_the_left_page_and_its_notes_on_the_right(
    qapp: QApplication,
) -> None:
    view = shown(qapp, "day")
    hours = canvas(view)
    assert [(track.day, track.axis, track.first, track.last) for track in hours.tracks] == [
        (THURSDAY, Axis.DOWN, 0, 1440)
    ]
    assert [
        key for key in ("school", "dinner", "essay-1", "chem-1") if hours.block_rect(key, 3) is None
    ] == []
    assert view.findChild(QWidget, "timelineNotesPage") is not None
    heading = view.findChild(QPushButton, "timelineDayHead")
    assert (heading.title.text(), heading.chip.text(), heading.chip.isVisible()) == ("Thursday", "17", True)


def test_day_sums_the_day_up_says_what_is_next_and_lists_what_is_due_with_nothing_to_write_in(
    qapp: QApplication,
) -> None:
    view = shown(qapp, "day")
    assert texts(view, "timelineLabel") == ["Today", "Next", "Due this week"]
    assert texts(view, "timelineTrayLabel") == ["Not placed yet"]
    assert texts(view, "timelineSum") == ["2 h 30 min planned · 0 done"]
    shares = list(zip(texts(view, "timelineShare"), texts(view, "timelineShareLength"), strict=True))
    assert shares == [("School", "6 h 30 min"), ("Meals", "30 min"), ("Homework", "2 h 30 min")]
    (line,) = view.findChildren(QLabel, "timelineNext")
    assert plain(line) == "Dinner at 18:00, in 4 h 20 min"
    assert [when.text() for when in view.findChildren(QLabel, "timelineDueWhen") if when.isVisible()] == [
        "due Sun 20 Sep · Not placed yet",
        "due Tue 15 Sep · placed Mon 15:45",
        "due Fri 18 Sep · placed Thu 18:45",
        "due Thu 17 Sep · placed Thu 20:00",
    ]
    # No ruled space for notes: it looked writable and kept nothing.
    assert view.findChild(QWidget, "timelineRuled") is None
    assert [chip.held.title for chip in view.findChildren(TrayChip) if chip.isVisible()] == ["Poster-1"]


def test_another_day_is_named_for_itself_and_claims_no_next(qapp: QApplication) -> None:
    view = shown(qapp, "day")
    kept = scroll_of(view)
    view.show_week(replace(view.scene, iso_day="2026-09-14"))
    qapp.processEvents()
    assert texts(view, "timelineLabel") == ["Monday", "Due this week"]
    assert view.findChild(QPushButton, "timelineDayHead").title.text() == "Monday"
    assert [track.day for track in canvas(view).tracks] == [0]
    assert scroll_of(view) is kept


def test_the_days_blocks_say_their_length_as_well_as_their_times(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = drawn_words(monkeypatch, shown(qapp, "day"))
    assert any("6 h 30 min" in words for words in day)


def test_a_half_hour_on_day_says_its_name_and_times(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A half-hour is too short on Day for a line at the body size; the mock-up writes it smaller
    rather than leave Dinner a coloured bar."""
    said = drawn_words(monkeypatch, shown(qapp, "day"))
    assert "Dinner" in said and "18:00–18:30" in said


def test_now_is_written_with_its_time_on_day_too(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "15:40" in drawn_words(monkeypatch, shown(qapp, "day", clock="15:40"))
