"""Retro desktop's Day: Week.exe opened on one live column, with the day's summary in the folder view
beside it."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.hours.zoom import HoursScroll  # noqa: E402
from desktop.tests.week.support_retro import NBSP, shown, task, text  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-retro-test"])
    yield application


def test_day_opens_week_exe_on_one_live_column(qapp: QApplication) -> None:
    view = shown(qapp, 1280, 820, surface="day", iso_day="2026-09-17")
    assert text(view, "retroTitle-week") == "Week.exe - Thursday 17 September"
    assert task(view, "week").text() == "Week.exe"
    scroll = view.findChild(HoursScroll, "retroDayScroll")
    assert scroll is not None
    assert [track.day for track in scroll.canvas.tracks] == [3]
    assert scroll.canvas.hand is view.hand
    assert scroll.canvas.block_rect("school", 3) is not None
    assert view.findChild(TrayChip, "retroNoteWaiting0").isVisible()


def test_day_has_the_folder_web_view_with_the_days_summary(qapp: QApplication) -> None:
    """Thursday has School 08:00 to 14:30, Dinner 18:00, Essay-1 18:45 and Chem-1 20:00. Planned is
    the homework only, 2 h 30 min, and three blocks start after 13:40. It is free from School's end
    to Dinner, and from Chem-1's end to 22:00. The quarter hours between Dinner, Essay-1 and Chem-1
    are too short to list."""
    view = shown(qapp, 1280, 820, surface="day", iso_day="2026-09-17")
    said = [label.text() for label in view.findChildren(QLabel) if label.objectName().startswith("retroWeb")]
    assert said == [
        "Thursday",
        "17 September",
        f"2{NBSP}h{NBSP}30{NBSP}min planned, 3 still to come.",
        "Your day",
        "School",
        "6 h 30 min",
        "Homework",
        "2 h 30 min",
        "Meals",
        "30 min",
        "Free from now",
        "14:30–18:00",
        "3 h 30 min",
        "21:30–22:00",
        "30 min",
    ]
    assert text(view, "retroStatusNow") == "3 still to come"
    other = shown(qapp, 1280, 820, surface="day", iso_day="2026-09-18")
    said = [label.text() for label in other.findChildren(QLabel) if label.objectName().startswith("retroWeb")]
    assert "Free from now" not in said and "Free" in said
    assert not other.findChild(QLabel, "retroStatusNow").isVisible()
