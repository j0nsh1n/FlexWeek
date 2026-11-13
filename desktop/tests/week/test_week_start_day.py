"""The week can start on any of the seven days. The choice is kept per computer, and the calendar
popup follows it. Stored weeks stay keyed by their Monday either way."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QWidget

from desktop.native import fields
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture()
def kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The per-computer file, in a temporary folder for each test."""
    path = tmp_path / "week-start.json"
    monkeypatch.setattr(fields, "_week_starts_file", lambda: path)
    return path


def test_a_new_computer_starts_the_week_on_monday(kept: Path) -> None:
    assert fields.week_starts_on() == "monday"
    assert fields.first_day_of_week() == Qt.DayOfWeek.Monday


SEVEN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@pytest.mark.parametrize(
    ("start", "qt_day"),
    (
        ("tuesday", Qt.DayOfWeek.Tuesday),
        ("wednesday", Qt.DayOfWeek.Wednesday),
        ("thursday", Qt.DayOfWeek.Thursday),
        ("friday", Qt.DayOfWeek.Friday),
        ("saturday", Qt.DayOfWeek.Saturday),
    ),
)
def test_any_weekday_can_be_saved_and_drives_the_calendar_popup(
    qapp: QApplication,
    kept: Path,
    start: str,
    qt_day: Qt.DayOfWeek,
) -> None:
    fields.save_week_starts_on(start)
    assert fields.week_starts_on() == start
    assert fields.first_day_of_week() == qt_day
    assert fields.LookCalendar().firstDayOfWeek() == qt_day


def test_a_saved_sunday_is_read_back_and_drives_the_calendar_popup(
    qapp: QApplication,
    kept: Path,
) -> None:
    fields.save_week_starts_on("sunday")
    assert fields.week_starts_on() == "sunday"
    assert fields.first_day_of_week() == Qt.DayOfWeek.Sunday
    assert fields.LookCalendar().firstDayOfWeek() == Qt.DayOfWeek.Sunday


@pytest.mark.parametrize(
    ("start", "expected"),
    (
        ("monday", [0, 1, 2, 3, 4, 5, 6]),
        ("sunday", [6, 0, 1, 2, 3, 4, 5]),
        ("wednesday", [2, 3, 4, 5, 6, 0, 1]),
        ("saturday", [5, 6, 0, 1, 2, 3, 4]),
    ),
)
def test_my_day_dial_strip_follows_the_first_day_of_the_week(
    qapp: QApplication,
    kept: Path,
    start: str,
    expected: list[int],
) -> None:
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.dial import DayDialView, DialFace
    from desktop.native.weekmodel import build_week

    fields.save_week_starts_on(start)
    week = build_week("2026-09-21", [], {}, None)
    strip = DayDialView()._week(Scene(week, 2, 0), 2)

    assert [face.day for face in strip.findChildren(DialFace)] == expected
    strip.deleteLater()


def test_a_damaged_week_start_file_falls_back_to_monday(kept: Path) -> None:
    kept.write_text("{not json", encoding="utf-8")
    assert fields.week_starts_on() == "monday"
    kept.write_text('{"week_starts_on": "someday"}', encoding="utf-8")
    assert fields.week_starts_on() == "monday"


def test_a_file_written_before_any_day_could_be_picked_still_reads(kept: Path) -> None:
    kept.write_text('{"week_starts_on":"sunday"}', encoding="utf-8")
    assert fields.week_starts_on() == "sunday"


def test_only_the_seven_day_names_can_be_saved(kept: Path) -> None:
    for wrong in ("someday", "Wednesday", ""):
        with pytest.raises(ValueError):
            fields.save_week_starts_on(wrong)
    assert not kept.exists()


def _setup_page(qapp: QApplication):
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


def test_the_setup_week_question_is_saved_when_kept_and_not_when_skipped(
    qapp: QApplication,
    kept: Path,
) -> None:
    from desktop.native.setup import HOMEWORK, WEEK

    host, setup = _setup_page(qapp)
    try:
        choice = setup.findChild(QComboBox, "setupWeekStart")
        assert [choice.itemText(at) for at in range(choice.count())] == SEVEN
        assert choice.currentText() == "Monday"
        assert choice.accessibleName() == "Week starts on"
        assert (
            setup.findChild(QLabel, "setupWeekStartHint").text()
            == "The Week view always runs Monday to Sunday."
        )
        setup._show(WEEK)
        choice.setCurrentIndex(SEVEN.index("Wednesday"))
        setup._leave(HOMEWORK, keep=False)
        assert not kept.exists()
        setup._show(WEEK)
        choice.setCurrentIndex(SEVEN.index("Wednesday"))
        setup._leave(HOMEWORK, keep=True)
        assert fields.week_starts_on() == "wednesday"
    finally:
        host.close()
        host.deleteLater()


def test_the_settings_control_saves_the_week_start_on_this_computer(
    qapp: QApplication,
    kept: Path,
) -> None:
    from desktop.native.settings import SettingsPage

    host = QWidget()
    page = SettingsPage(host, {"clock_24h": False}, {"preset": "default", "knobs": {}}, {})
    try:
        choice = page.findChild(QComboBox, "prefWeekStart")
        assert [choice.itemText(at) for at in range(choice.count())] == SEVEN
        assert choice.currentText() == "Monday"
        assert (
            page.findChild(QLabel, "prefWeekStartNote").text()
            == "The Week view always runs Monday to Sunday."
        )
        choice.setCurrentIndex(SEVEN.index("Sunday"))
        assert fields.week_starts_on() == "sunday"
        assert fields.first_day_of_week() == Qt.DayOfWeek.Sunday
        choice.setCurrentIndex(SEVEN.index("Thursday"))
        assert fields.week_starts_on() == "thursday"
        assert fields.first_day_of_week() == Qt.DayOfWeek.Thursday
    finally:
        host.close()
        host.deleteLater()


def _pills_in_order(picker: QWidget) -> list[str]:
    line = picker.layout()
    found = (line.itemAt(at).widget() for at in range(line.count()))
    return [widget.accessibleName() for widget in found if widget is not None]


@pytest.mark.parametrize(
    ("start", "order"),
    (
        ("monday", SEVEN),
        ("wednesday", ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Monday", "Tuesday"]),
        ("sunday", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]),
    ),
)
def test_day_buttons_start_on_the_chosen_day_and_still_mean_the_same_weekday(
    qapp: QApplication, kept: Path, start: str, order: list[str]
) -> None:
    kept.write_text(f'{{"week_starts_on": "{start}"}}', encoding="utf-8")
    picker = fields.DayPicker([5], "schoolDay")
    try:
        assert _pills_in_order(picker) == order
        assert picker.days() == [5]
        assert picker.findChild(QWidget, "schoolDay5").accessibleName() == "Saturday"
        picker.findChild(QWidget, "schoolDay0").click()
        assert picker.days() == [0, 5]
    finally:
        picker.deleteLater()


def test_day_buttons_that_carry_the_open_weeks_dates_keep_its_monday_order(
    qapp: QApplication, kept: Path
) -> None:
    kept.write_text('{"week_starts_on": "wednesday"}', encoding="utf-8")
    picker = fields.DayPicker([3], "homeworkWhenDay", dated=True)
    try:
        assert _pills_in_order(picker) == SEVEN
    finally:
        picker.deleteLater()
