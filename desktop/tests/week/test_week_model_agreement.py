"""The week model is the one reading of the week every layout shares. Its placement rules are tested
in engine/engine/tests/desk_weekmodel.rs and the slack words in engine/engine/tests/week_slack_words.rs;
this file keeps the agreement with what the week table draws, the wrappers' own sentences, and the
week every layout test builds from (support_weekview)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.hours.classic import ClassicWeek
from desktop.native.hours.hand import Hand, Verdict
from desktop.native.weekmodel import build_week, homework_time_sentence
from desktop.tests.week.support_weekview import BLOCKS, HOMEWORK, TRACE, WEEK, block
from desktop.tests.window_support import qapp  # noqa: F401


def test_homework_time_sentence_includes_overdue_carried_and_unplaced_work() -> None:
    assert (
        homework_time_sentence(
            [
                {"id": "bio", "left_over_state": "overdue", "remaining_min": 60},
                {"id": "chem", "left_over_state": "left_from_last_week", "remaining_min": 30},
            ],
            [{"assignment_id": "chem", "minutes": 30}, {"assignment_id": "art", "minutes": 15}],
        )
        == "1 overdue · 1 left from last week · 45 min still needs a time"
    )
    assert (
        homework_time_sentence([{"id": "bio", "left_over_state": "overdue", "remaining_min": 60}], [])
        == "1 overdue"
    )
    assert homework_time_sentence([], []) == "Everything has a time."


def test_the_built_week_upgrades_plenty_when_due_within_24_hours() -> None:
    now = datetime(2026, 11, 5, 19, 0)
    due = "2026-11-06T18:00"
    blocks = [block("essay-1", "flexible", [3], "20:00", 30, assignment_id="essay")]
    homework = {"essay": {"id": "essay", "title": "History essay", "due": due, "completed": False}}
    trace = {
        "placed": [],
        "unplaced": [],
        "explanations": [{"block_id": "essay-1", "slack_status": "ok"}],
    }
    model = build_week("2026-11-02", blocks, homework, trace)
    found = next(item for item in model.occurrences if item.block_id == "essay-1")
    assert found.slack_words(now) == "Tight"
    assert found.slack_words(None) == "Plenty of time"


def test_the_model_places_every_block_where_the_week_calendar_draws_it(
    qapp: QApplication,
) -> None:
    host = QWidget()
    calendar = ClassicWeek(Hand(lambda block_id, from_day, span: Verdict(False, ""), host), host)
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    calendar.set_week(week, None, None)
    calendar.resize(980, 640)
    calendar.hours.relayout()
    hours = calendar.hours
    drawn = {
        (item.block_id, item.span.day, item.span.start)
        for track in hours.tracks
        for item, _rect in hours.drawn(track)
    }
    modelled = {(item.block_id, item.day, item.start) for item in week.occurrences}
    assert modelled == drawn
    assert len(drawn) == 15
    host.deleteLater()
