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
    ("week_start", "expected"),
    (
        # Monday 21 September 2026, and the weeks from Sunday 20, Wednesday 23 and Saturday 26.
        ("2026-09-21", ["Mon 21", "Tue 22", "Wed 23", "Thu 24", "Fri 25", "Sat 26", "Sun 27"]),
        ("2026-09-20", ["Sun 20", "Mon 21", "Tue 22", "Wed 23", "Thu 24", "Fri 25", "Sat 26"]),
        ("2026-09-23", ["Wed 23", "Thu 24", "Fri 25", "Sat 26", "Sun 27", "Mon 28", "Tue 29"]),
        ("2026-09-26", ["Sat 26", "Sun 27", "Mon 28", "Tue 29", "Wed 30", "Thu 1", "Fri 2"]),
    ),
)
def test_my_day_dial_strip_shows_the_open_week_in_order_named_from_its_dates(
    qapp: QApplication,
    week_start: str,
    expected: list[str],
) -> None:
    from desktop.native.layouts.base import Scene
    from desktop.native.layouts.dial import DayDialView, DialFace
    from desktop.native.weekmodel import build_week

    week = build_week(week_start, [], {}, None)
    strip = DayDialView()._week(Scene(week, 2, 0), 2)

    assert [face.day for face in strip.findChildren(DialFace)] == [0, 1, 2, 3, 4, 5, 6]
    names = [str(item.text()) for item in strip.findChildren(QLabel, "dialMiniName")]
    dates = [str(item.text()) for item in strip.findChildren(QLabel, "dialMiniDate")]
    assert [f"{name} {number}" for name, number in zip(names, dates, strict=True)] == expected
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
        # Week starts on the chosen day too, so the page no longer says it runs Monday to Sunday.
        words = [label.text() for label in setup.findChildren(QLabel)]
        assert not [text for text in words if "Monday to Sunday" in text], words
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


def test_setup_school_and_activity_days_start_on_a_day_as_soon_as_it_is_picked(
    qapp: QApplication,
    kept: Path,
) -> None:
    host, setup = _setup_page(qapp)
    try:
        setup._add_activity("Soccer", [1, 3])
        choice = setup.findChild(QComboBox, "setupWeekStart")
        choice.setCurrentIndex(SEVEN.index("Wednesday"))
        qapp.processEvents()
        wednesday_first = ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Monday", "Tuesday"]
        assert _pills_in_order(setup.school_days) == wednesday_first
        assert _pills_in_order(setup.activities[-1].days) == wednesday_first
        # Nothing is saved until the page is kept, and each pill still means its weekday.
        assert not kept.exists()
        assert setup.school_days.days() == [0, 1, 2, 3, 4]
        assert setup.activities[-1].days.days() == [1, 3]
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
        words = [label.text() for label in page.findChildren(QLabel)]
        assert not [text for text in words if "Monday to Sunday" in text], words
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


def test_day_buttons_that_carry_the_open_weeks_dates_start_on_its_first_day(
    qapp: QApplication, kept: Path
) -> None:
    from desktop.native.calendar import day_full_names
    from desktop.native.widgets import dated_day_labels

    kept.write_text('{"week_starts_on": "wednesday"}', encoding="utf-8")
    picker = fields.DayPicker([3], "homeworkWhenDay", dated=True)
    try:
        # The week from Wednesday 4 November 2026; day 3 is Saturday 7.
        picker.set_day_labels(dated_day_labels("2026-11-04"), day_full_names("2026-11-04"))
        assert _pills_in_order(picker) == [
            "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Monday", "Tuesday"
        ]
        assert [button.text() for button in picker.buttons][:2] == ["Wed\n4", "Thu\n5"]
        assert picker.days() == [3]
        assert picker.buttons[3].text() == "Sat\n7"
    finally:
        picker.deleteLater()


def test_a_blocks_day_buttons_are_the_open_weeks_days_named_from_their_dates(
    qapp: QApplication, kept: Path
) -> None:
    kept.write_text('{"week_starts_on": "wednesday"}', encoding="utf-8")
    # A block on the first day of the week from Wednesday 4 November 2026.
    picker = fields.DayPicker([0], "blockDay", week_start="2026-11-04")
    try:
        assert _pills_in_order(picker) == [
            "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Monday", "Tuesday"
        ]
        shown = [button.text() for button in picker.buttons]
        assert shown == ["Wed", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]
        # Monday 9 November is day 5 of that week, as the block's days count.
        picker.findChild(QWidget, "blockDay5").click()
        assert picker.days() == [0, 5]
    finally:
        picker.deleteLater()
