# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
"""Setup's pages on their own: what a page shows and refuses, what a look tried and skipped does, the
rail, the sports rows, and the words each design and control goes by."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QApplication, QComboBox, QDateTimeEdit, QLabel, QPushButton, QWidget

from desktop.native.layouts.registry import layouts_for
from desktop.native.setup import (
    COLOURS,
    DONE,
    FIRST,
    HOMEWORK,
    LOOK,
    REMINDERS,
    STYLES,
    WEEK,
    ActivityRow,
    QuarterTime,
    SetupPage,
    activity_category_for,
)
from desktop.tests.setup.support_wizard import opened, state
from desktop.tests.window_support import qapp  # noqa: F401

SPOTIFY = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"


def test_the_style_page_previews_plain_calendar_as_it_opens(qapp: QApplication) -> None:
    setup = SetupPage()
    setup.motion = "off"
    shown: list[dict] = []
    setup.previewed.connect(shown.append)
    setup.open(state())
    assert shown, "Style opens with a live preview, not the system's dark look"
    assert shown[0]["pack"] == "light-frost"
    assert shown[0]["layout"]["main"] == "classic"
    setup.close()


def test_retros_style_note_describes_the_feel_not_the_layout_name(qapp: QApplication) -> None:
    setup = opened(qapp)
    retro = next(style for style in STYLES if style.key == "retro")
    assert retro.note == "A 90s desktop, with large text"
    setup.carousel.go_to("retro")
    qapp.processEvents()
    assert setup.carousel.note.text() == retro.note
    assert "Retro desktop" not in retro.note
    setup.close()


def test_a_look_tried_and_skipped_is_put_back(qapp: QApplication) -> None:
    setup = opened(qapp)
    shown: list[dict] = []
    kept: list[object] = []
    setup.previewed.connect(shown.append)
    setup.left.connect(lambda _step, _to, answer: kept.append(answer))
    setup.style_cards["night"].chosen.emit()
    assert shown[-1]["pack"] == "dark-frost" and shown[-1]["layout"]["main"] == "timeline"
    setup.skip.click()
    assert kept == [None]
    assert shown[-1]["pack"] == "system" and shown[-1]["layout"]["main"] == "classic"
    setup.close()


def test_choose_my_own_look_goes_through_look_and_colours(qapp: QApplication) -> None:
    setup = opened(qapp)
    kept: list[tuple[int, object]] = []
    setup.left.connect(lambda step, _to, answer: kept.append((step, answer)))
    own = setup.findChild(QPushButton, "setupOwnLook")
    # Words, not an arrow drawn after them.
    assert own.text() == "Choose my own look instead"
    own.click()
    assert setup.step == LOOK
    setup.look_cards["timeline"].chosen.emit()
    setup.next.click()
    assert setup.step == COLOURS
    setup.colours.buttons()[3].click()
    setup.text_size.buttons()[2].click()
    setup.next.click()
    assert setup.step == WEEK
    step, answer = kept[-1]
    assert step == COLOURS and isinstance(answer, dict)
    assert answer["layout"]["main"] == "timeline"
    assert answer["layout"]["options"]["timeline"]["look"] == "pack:dark-frost"
    assert answer["look"]["knobs"]["text"] == "large"
    setup.back.click()
    assert setup.step == COLOURS, "Back from the week returns to the look the student built"
    setup.close()


def test_the_day_screen_chips_are_one_choice_across_two_rows(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(LOOK)
    setup._show(COLOURS)
    qapp.processEvents()
    chips = setup.day_screen
    assert chips.experimental_heading.text() == "Experimental styles"
    assert chips.experimental_heading.isVisibleTo(setup)
    dial, one = chips.buttons()
    one.click()
    assert chips.value() == "one" and not dial.isChecked()
    dial.click()
    assert chips.value() == "dial" and not one.isChecked()
    assert setup._layout["day"] == "dial"
    setup.close()


def test_a_step_already_seen_can_be_jumped_to_from_the_rail(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup.skip.click()
    setup.skip.click()
    assert setup.step == HOMEWORK
    setup.rail_items[1].click()
    assert setup.step == WEEK
    assert not setup.rail_items[4].isEnabled(), "a step not reached yet is shown out of reach"
    setup._jump(FIRST)
    assert setup.step == WEEK, "and stays out of reach"
    setup.close()


def test_a_spotify_alarm_needs_a_spotify_link(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(REMINDERS)
    setup.tone_buttons["spotify"].setChecked(True)
    assert setup.spotify.isEnabled()
    setup.spotify.setText("https://example.com/song")
    setup.next.click()
    assert setup.step == REMINDERS
    assert setup.error.text() == (
        "Paste a link that starts with https://open.spotify.com, or pick another sound."
    )
    setup.spotify.setText(SPOTIFY)
    setup.next.click()
    assert setup.step == FIRST
    assert setup.error.text() == ""
    setup.close()


def test_the_alarm_sounds_each_have_a_play_button_named_for_them(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(REMINDERS)
    qapp.processEvents()
    body = setup.pages[REMINDERS]
    plays = [button for button in body.findChildren(QPushButton, "setupPlay") if button.isVisibleTo(setup)]
    tones = [key for key in setup.tone_buttons if key != "spotify"]
    assert len(plays) == len(tones)
    for tone, play in zip(tones, plays, strict=True):
        assert play.accessibleName() == f"Play {setup.tone_buttons[tone].text()}", tone
    setup.close()


def test_school_has_to_end_after_it_starts(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(WEEK)
    setup.school_times.set_span("15:00", 0)
    setup.next.click()
    # The problem is said under End, which keeps the keyboard; the bar only counts what is left.
    assert setup.step == WEEK and setup.error.text() == "1 thing to fix on this step"
    end = setup.school_times.end
    assert end.problem() == "End needs to be later than Start (3:00 PM)." and end.hasFocus()
    setup.school_days.set_days([])
    setup.next.click()
    assert setup.step == HOMEWORK, "no school days means no school, so its hours do not matter"
    setup.close()


def test_setup_refuses_a_work_window_that_ends_before_it_starts(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(HOMEWORK)
    setup.work_editor.set_windows([{"days": [0], "start": "15:00", "end": "16:00"}])
    row = setup.work_editor.findChild(QWidget, "workWindowRow")
    ends = row.findChild(QComboBox, "workWindowEnd")
    ends.setCurrentIndex(ends.findData("14:45"))
    setup.next.click()
    assert setup.step == HOMEWORK
    assert row.findChild(QLabel, "validationError").text() == "End needs to be later than Start (3:00 PM)."
    setup.close()


def test_the_planning_hours_presets_are_chips_that_each_add_a_row(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(HOMEWORK)
    qapp.processEvents()
    editor = setup.work_editor
    note = editor.findChild(QLabel, "workWindowsPresetsNote")
    assert note.text() == "Each adds a row of hours you can change."
    after = editor.findChild(QPushButton, "workWindowPresetAfterschool")
    assert after.text() == "+ After school" and after.property("chip") is True
    assert not after.isCheckable(), "a chip never shows as picked"
    after.click()
    assert editor.windows() == [{"days": [0, 1, 2, 3, 4], "start": "15:30", "end": "18:00"}]
    setup.close()


@pytest.mark.parametrize(
    "name,label",
    [
        ("workWindowPresetAfterschool", "+ After school"),
        ("workWindowPresetEvenings", "+ Evenings"),
        ("workWindowPresetWeekendmornings", "+ Weekend mornings"),
    ],
)
def test_each_planning_hours_chip_adds_one_row_and_says_what_it_adds(
    qapp: QApplication, name: str, label: str
) -> None:
    setup = opened(qapp)
    setup._show(HOMEWORK)
    chip = setup.work_editor.findChild(QPushButton, name)
    assert chip is not None and chip.text() == label
    chip.click()
    assert len(setup.work_editor.windows()) == 1
    setup.close()


def test_two_activities_keep_their_own_days_and_an_untouched_row_adds_nothing(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(WEEK)
    assert [block["id"] for block in setup.week_blocks()] == ["school"], "the empty row is not an activity"
    setup.activities[0].name.setText("Soccer")
    setup.activities[0].days.set_days([1, 3])
    setup._add_activity(title="", days=[0], start="16:00", minutes=60)
    setup._add_activity(title="Band", days=[], start="17:00", minutes=60)
    made = {block["title"]: block["days"] for block in setup.week_blocks() if block["id"] != "school"}
    assert made == {"Soccer": [1, 3], "Sport or club": [0]}, "a row with days but no name still counts"
    setup.close()


def test_setup_saves_the_chosen_sports_category_and_restores_it(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(WEEK)
    row = setup.activities[0]
    row.name.setText("Band")
    row.days.set_days([1])
    choice = row.findChild(QComboBox, "setupActivityCategory")
    assert choice is not None, "Each entry needs a Sports or Activity choice"
    assert choice.currentData() == "extra"
    choice.setCurrentIndex(choice.findData("exercise"))
    blocks = setup.week_blocks()
    assert next(block for block in blocks if block["title"] == "Band")["category"] == "exercise"
    setup._state.blocks = blocks
    setup._fill_week()
    assert setup.activities[0].findChild(QComboBox, "setupActivityCategory").currentData() == "exercise"
    choice = setup.activities[0].findChild(QComboBox, "setupActivityCategory")
    choice.setCurrentIndex(choice.findData("extra"))
    assert next(block for block in setup.week_blocks() if block["title"] == "Band")["category"] == "extra"
    setup.close()


def test_a_typed_sport_name_is_sports_and_the_student_can_still_change_it(qapp: QApplication) -> None:
    assert activity_category_for("Soccer") == "exercise"
    assert activity_category_for("swim practice") == "exercise"
    assert activity_category_for("Piano practice") == "extra"
    assert activity_category_for("Band practice") == "extra"
    assert activity_category_for("Band") == "extra"
    row = ActivityRow()
    assert row.category.currentData() == "extra"
    row.name.setText("Soccer")
    assert row.category.currentData() == "exercise"
    row.category.setCurrentIndex(row.category.findData("extra"))
    row.category.activated.emit(row.category.currentIndex())
    row.name.setText("Football")
    assert row.category.currentData() == "extra"
    row.deleteLater()


def test_a_restored_activity_keeps_the_category_the_student_chose(qapp: QApplication) -> None:
    setup = opened(qapp)
    setup._show(WEEK)
    row = setup.activities[0]
    row.name.setText("Soccer")
    row.days.set_days([1])
    choice = row.findChild(QComboBox, "setupActivityCategory")
    assert choice.currentData() == "exercise"
    choice.setCurrentIndex(choice.findData("extra"))
    choice.activated.emit(choice.currentIndex())
    setup._state.blocks = setup.week_blocks()
    setup._fill_week()
    assert setup.activities[0].name.text() == "Soccer"
    assert setup.activities[0].findChild(QComboBox, "setupActivityCategory").currentData() == "extra"
    setup.close()


def test_a_time_steps_a_quarter_hour_and_a_typed_one_keeps_its_minute(qapp: QApplication) -> None:
    """School that starts at 08:05 starts at 08:05. It was moved to 08:00 without a word."""
    field = QuarterTime("08:00")
    field.setCurrentSection(QDateTimeEdit.Section.MinuteSection)
    field.stepBy(1)
    assert field.hhmm() == "08:15"
    field.stepBy(-2)
    assert field.hhmm() == "07:45"
    field.setTime(QTime(8, 7))
    field.editingFinished.emit()
    assert field.hhmm() == "08:07"
    field.stepBy(1)
    assert field.hhmm() == "08:15", "the arrows go on to the quarter hour either side"
    field.setTime(QTime(8, 7))
    field.stepBy(-1)
    assert field.hhmm() == "08:00"


def test_setup_calls_each_design_by_the_one_name_settings_uses(qapp: QApplication) -> None:
    """'Calendar · Today's app' was two names for one design."""
    setup = opened(qapp)
    for card in [*setup.style_cards.values(), *setup.look_cards.values()]:
        assert "·" not in card.accessibleName() + card.accessibleDescription(), card.accessibleName()
    assert setup.look_cards["classic"].accessibleName() == "Today's app"
    assert setup.look_cards["timeline"].accessibleName() == "Timeline"
    assert all("Today's app" not in card.accessibleDescription() for card in setup.style_cards.values())
    # The day screens, offered by name on the colours page.
    chips = [button.text() for button in setup.day_screen.buttons()]
    assert chips == [spec.label for spec in (*layouts_for("day", False), *layouts_for("day", True))]
    setup._show(DONE)
    assert setup.summary_text()[0].startswith("Today's app in "), setup.summary_text()[0]
    assert "·" not in setup.summary_text()[0]
    setup.close()
