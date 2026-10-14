"""The week can start on Monday or Sunday. The choice is kept per computer, and the calendar popup
follows it. Stored weeks stay keyed by their Monday either way."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel

    from desktop.native import fields


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-week-start-test"])


@pytest.fixture()
def kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The per-computer file, in a temporary folder for each test."""
    path = tmp_path / "week-start.json"
    monkeypatch.setattr(fields, "_week_starts_file", lambda: path)
    return path


def test_a_new_computer_starts_the_week_on_monday(kept: Path) -> None:
    assert fields.week_starts_on() == "monday"
    assert fields.first_day_of_week() == Qt.DayOfWeek.Monday


def test_saved_sunday_is_read_back_and_drives_the_calendar_popup(qapp: QApplication, kept: Path) -> None:
    fields.save_week_starts_on("sunday")
    assert fields.week_starts_on() == "sunday"
    assert fields.first_day_of_week() == Qt.DayOfWeek.Sunday
    assert fields.LookCalendar().firstDayOfWeek() == Qt.DayOfWeek.Sunday


@pytest.mark.parametrize(
    ("start", "expected"),
    (("monday", [0, 1, 2, 3, 4, 5, 6]), ("sunday", [6, 0, 1, 2, 3, 4, 5])),
)
def test_my_day_dial_strip_order(qapp: QApplication, kept: Path, start: str, expected: list[int]) -> None:
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.dial import DayDialView, DialFace
    from desktop.native.weekmodel import build_week

    fields.save_week_starts_on(start)
    week = build_week("2026-09-21", [], {}, None)
    strip = DayDialView()._week(Scene(week, 2, 0), 2)

    assert [face.day for face in strip.findChildren(DialFace)] == expected
    strip.deleteLater()


def test_a_damaged_file_falls_back_to_monday(kept: Path) -> None:
    kept.write_text("{not json", encoding="utf-8")
    assert fields.week_starts_on() == "monday"
    kept.write_text('{"week_starts_on": "saturday"}', encoding="utf-8")
    assert fields.week_starts_on() == "monday"


def test_only_monday_or_sunday_can_be_saved(kept: Path) -> None:
    with pytest.raises(ValueError):
        fields.save_week_starts_on("saturday")
    assert not kept.exists()


def _setup_page(qapp: QApplication):
    from PySide6.QtWidgets import QWidget

    from desktop.native.calendar import monday_of
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import pack_stylesheet, resolved_palette
    from desktop.native.setup import SetupPage, SetupState
    from desktop.native.widgets import control_art

    palette = resolved_palette("light-frost", False, None)
    host = QWidget()
    host.setStyleSheet(pack_stylesheet("light-frost", False, None, "default", palette, control_art(palette)))
    setup = SetupPage(host)
    setup.motion = "off"
    setup.set_palette(palette)
    setup.open(
        SetupState(
            "light-frost",
            {"preset": "default", "knobs": {}},
            sanitize_layout(None),
            {},
            [],
            monday_of("2026-09-23"),
        )
    )
    host.resize(1600, 800)
    setup.resize(1600, 800)
    host.show()
    qapp.processEvents()
    return host, setup


def test_the_week_page_question_is_saved_when_kept_and_not_when_skipped(
    qapp: QApplication, kept: Path
) -> None:
    from desktop.native.setup import HOMEWORK, WEEK

    host, setup = _setup_page(qapp)
    try:
        assert setup.week_start_buttons["monday"].isChecked()
        assert (
            setup.findChild(QLabel, "setupWeekStartHint").text()
            == "The Week view always runs Monday to Sunday."
        )
        setup._show(WEEK)
        setup.week_start_buttons["sunday"].setChecked(True)
        setup._leave(HOMEWORK, keep=False)
        assert not kept.exists()
        setup._show(WEEK)
        setup.week_start_buttons["sunday"].setChecked(True)
        setup._leave(HOMEWORK, keep=True)
        assert fields.week_starts_on() == "sunday"
    finally:
        host.close()
        host.deleteLater()


def test_the_settings_control_saves_the_week_start_on_this_computer(
    qapp: QApplication, kept: Path
) -> None:
    from PySide6.QtWidgets import QWidget

    from desktop.native.settings import SettingsPage

    host = QWidget()
    page = SettingsPage(host, {"clock_24h": False}, {"preset": "default", "knobs": {}}, {})
    try:
        assert page.week_start.currentData() == "monday"
        assert (
            page.findChild(QLabel, "prefWeekStartNote").text()
            == "The Week view always runs Monday to Sunday."
        )
        page.week_start.setCurrentIndex(1)
        assert fields.week_starts_on() == "sunday"
        assert fields.first_day_of_week() == Qt.DayOfWeek.Sunday
    finally:
        host.close()
        host.deleteLater()
