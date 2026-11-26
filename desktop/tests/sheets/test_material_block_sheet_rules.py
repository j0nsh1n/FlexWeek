# ruff: noqa: F811
"""The Material fixed time sheet's rules a student relies on: what Delete looks like, the repeat notes and
the Apply to row, End and Start, the missed-day switch, the category guessed from the start and a run of
days named as a range.

The week the fixtures build: School Monday to Friday 08:00 to 14:30, the clock Thursday 19:00 (so Tuesday's
and Thursday's Soccer practice at 16:00 are behind us). Expected words come from the rules, not from reading
what the sheet returns.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import named, pump, visuals  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)
from desktop.tests.sheets.support_prompt_walk import footer_buttons, prompt_item  # noqa: E402
from desktop.tests.sheets.support_soccer import soccer  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402

REPEAT_NOTE = "Pick every day it happens."
SERIES_NOTE = "Changes apply to every selected day in this series."


def _add(qapp: QApplication, shell: NativeWindow, **fields: object) -> None:
    shell.session.add_block(soccer(**fields))
    shell.session.save()
    settle(qapp, shell)


def _shown_texts(root: QObject) -> list[str]:
    return [
        str(item.property("text"))
        for item in visuals(root)
        if item.property("text") not in (None, "") and item.isVisible()
    ]


def _untick_every_day(sheets) -> None:
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)


# Delete -------------------------------------------------------------------------------------------------


def test_deleting_a_plain_fixed_time_has_a_red_delete_and_a_plain_cancel(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell)
    sheets.askDeleteBlock("soccer", 3)
    pump(qapp, 30)
    prompt = prompt_item(shell)
    assert prompt is not None
    error = str(shell._material_page.bridge.theme["error"]).lower()
    fills = {
        str(button.objectName()).removeprefix("prompt_"): QColor(button.property("fill")).name().lower()
        for button in footer_buttons(prompt)
    }
    assert set(fills) == {"stay", "delete"}
    assert fills["delete"] == error
    assert fills["stay"] != error
    sheets.forceClose()


# Repeat notes and the Apply to row ----------------------------------------------------------------------


def test_a_series_opened_for_all_its_days_says_changes_apply_to_every_selected_day(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell)
    sheets.editBlock("soccer", -1)
    assert sheets.form["seriesNote"] == SERIES_NOTE
    pump(qapp, 20)
    assert SERIES_NOTE in _shown_texts(shell._material_page.root)


def test_a_one_day_block_does_not_say_changes_apply_to_every_selected_day(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell, days=[4])
    sheets.editBlock("soccer", -1)
    assert sheets.form["seriesNote"] == ""
    pump(qapp, 20)
    assert SERIES_NOTE not in _shown_texts(shell._material_page.root)


def test_a_series_opened_on_one_day_shows_the_apply_to_row_instead_of_the_note(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell)
    sheets.editBlock("soccer", 3)
    assert sheets.form["seriesNote"] == ""
    assert sheets.form["showScope"] is True


def test_a_new_fixed_time_says_to_pick_more_days_to_repeat_it(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlock()
    sheets.setText("title", "Chess club")
    sheets.next()
    pump(qapp, 20)
    assert sheets.form["repeatNote"] == REPEAT_NOTE
    assert REPEAT_NOTE in _shown_texts(shell._material_page.root)


def test_the_repeat_note_goes_when_the_sheet_is_for_one_day_of_a_series(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell)
    sheets.editBlock("soccer", 3)
    assert sheets.form["repeatNote"] == ""
    sheets.setText("scope", "series")
    assert sheets.form["repeatNote"] == REPEAT_NOTE


def test_the_apply_to_row_is_hidden_for_a_block_that_does_not_repeat(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell, days=[3])
    sheets.editBlock("soccer", 3)
    assert sheets.form["showScope"] is False
    pump(qapp, 20)
    assert not any(item.isVisible() for item in named(shell._material_page.root, "editScope"))


def test_the_apply_to_row_shows_for_a_block_that_repeats(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell)
    sheets.editBlock("soccer", 3)
    pump(qapp, 20)
    assert any(item.isVisible() for item in named(shell._material_page.root, "editScope"))


# End and Start ------------------------------------------------------------------------------------------


def _new_hour_at(sheets, start: str) -> None:
    sheets.openBlock()
    sheets.setText("title", "Study")
    sheets.next()
    sheets.setText("start", start)


def test_a_start_moved_late_ends_the_day_and_says_so(shell: NativeWindow, sheets) -> None:
    """An hour starting at 23:30 can only run to the end of the day: 30 minutes."""
    _new_hour_at(sheets, "23:30")
    assert sheets.form["end"] == 24 * 60
    assert sheets.form["durationLine"] == (
        "End moved to the end of the day (12:00 AM). It's now 30 min, not 1 h."
    )


def test_a_start_that_moves_takes_the_end_with_it_to_keep_the_length(shell: NativeWindow, sheets) -> None:
    _new_hour_at(sheets, "17:00")
    sheets.setText("start", "18:00")
    assert sheets.form["end"] == 19 * 60
    assert sheets.form["durationLine"] == "End moved to 7:00 PM to keep it 1 h."


def test_an_end_set_by_hand_is_not_moved_when_the_start_moves(shell: NativeWindow, sheets) -> None:
    _new_hour_at(sheets, "17:00")
    sheets.setNumber("end", 20 * 60)
    sheets.setText("start", "16:00")
    assert sheets.form["end"] == 20 * 60
    assert sheets.form["durationLine"] == "4 h"


def test_a_block_ending_at_the_end_of_the_day_saves_and_reopens_unchanged(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    sheets.openBlock()
    sheets.setText("title", "Late class")
    sheets.next()
    _untick_every_day(sheets)
    sheets.toggleDay(4)
    sheets.setText("start", "23:00")
    assert sheets.form["end"] == 24 * 60
    sheets.next()
    sheets.setText("category", "extra")
    sheets.next()
    assert sheets.kind == ""
    made = next(item for item in shell.session.blocks if item["title"] == "Late class")
    assert (made["start"], made["duration_min"]) == ("23:00", 60)
    settle(qapp, shell)

    sheets.editBlock(made["id"], -1)
    assert sheets.form["start"] == "23:00"
    assert sheets.form["end"] == 24 * 60
    assert sheets.form["durationLine"] == "1 h"
    sheets.save()
    kept = next(item for item in shell.session.blocks if item["id"] == made["id"])
    assert (kept["start"], kept["duration_min"]) == ("23:00", 60)
    settle(qapp, shell)


# The missed day -----------------------------------------------------------------------------------------


def _holder(shell: NativeWindow, day: int) -> dict:
    return next(
        item
        for item in shell.session.blocks
        if item.get("title") == "Soccer practice" and day in (item.get("days") or [])
    )


def test_a_passed_block_offers_i_missed_it_and_ticking_it_marks_the_day_missed(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _add(qapp, shell)
    sheets.editBlock("soccer", 1)
    assert sheets.form["showMissed"] is True
    assert sheets.form["missedLabel"] == "I missed it on Tuesday"
    assert sheets.form["missed"] is False
    sheets.setFlag("missed", True)
    sheets.save()
    wait_until(qapp, lambda: 1 in (_holder(shell, 1).get("missed_days") or []), what="Tuesday to be missed")
    settle(qapp, shell)
    assert 3 not in (_holder(shell, 3).get("missed_days") or []), "Thursday is not marked"


def test_unticking_i_missed_it_undoes_the_missed_day(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _add(qapp, shell, missed_days=[1])
    sheets.editBlock("soccer", 1)
    assert sheets.form["missed"] is True
    sheets.setFlag("missed", False)
    sheets.save()
    assert sheets.kind == ""
    assert 1 not in (_holder(shell, 1).get("missed_days") or [])
    settle(qapp, shell)


# The guessed category and day ranges --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "guessed"),
    [
        ("07:30", "meals"),
        ("12:30", "meals"),
        ("18:00", "meals"),
        ("09:00", "class"),
        ("15:00", "extra"),
        ("21:00", "extra"),
    ],
)
def test_the_category_is_guessed_from_when_the_block_starts(sheets, start: str, guessed: str) -> None:
    """Meals windows: 7 to 8, 12 to 13 and 18 to 19:30, checked first. School hours are 08:00 to 14:30. Any
    other start is an extra."""
    _new_hour_at(sheets, start)
    assert sheets.form["category"] == guessed


def test_a_category_the_student_picked_is_not_guessed_over(sheets) -> None:
    _new_hour_at(sheets, "09:00")
    sheets.setText("category", "sport")
    sheets.setText("start", "12:30")
    assert sheets.form["category"] == "sport"


@pytest.mark.parametrize(
    ("days", "words"),
    [
        ([0, 1, 2, 3, 4], "Every Mon–Fri"),
        ([1, 2, 3], "Every Tue–Thu"),
        ([4, 5], "Every Fri and Sat"),
        ([0, 2, 4], "Every Mon, Wed and Fri"),
        ([0, 1, 2, 4], "Every Mon–Wed and Fri"),
    ],
)
def test_three_or_more_days_in_a_row_are_named_as_a_range(
    qapp: QApplication, shell: NativeWindow, sheets, days: list[int], words: str
) -> None:
    _add(qapp, shell, days=days)
    sheets.editBlock("soccer", days[0])
    assert [choice["label"] for choice in sheets.form["scopeChoices"]] == ["This day only", words]


def test_removed_days_show_unticked_are_not_counted_and_can_be_ticked_back_on(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    standing = soccer(id="activity-1", days=[0, 1, 2, 3, 4], removed_days=[2, 3, 4])
    shell.session.set_setup_blocks([soccer(id="activity-1", days=[0, 1, 2, 3, 4])])
    shell.session.add_block(standing)
    shell.session.save()
    settle(qapp, shell)

    sheets.editBlock("activity-1", 0)
    assert sheets.form["showScope"] is True
    assert [choice["label"] for choice in sheets.form["scopeChoices"]] == [
        "This day only",
        "Every Mon and Tue",
    ]
    sheets.setText("scope", "series")
    assert [day["value"] for day in sheets.form["days"] if day["on"]] == [0, 1]

    # Unticking every active day must be refused rather than silently saving only removed days.
    sheets.toggleDay(0)
    sheets.toggleDay(1)
    sheets.save()
    assert sheets.kind == "block"
    assert sheets.form["daysProblem"] != ""

    # Ticking Wednesday back on restores it while Thursday and Friday stay removed.
    sheets.toggleDay(0)
    sheets.toggleDay(1)
    sheets.toggleDay(2)
    sheets.save()
    settle(qapp, shell)
    saved = next(item for item in shell.session.blocks if item["id"] == "activity-1")
    assert saved["days"] == [0, 1, 2, 3, 4]
    assert saved["removed_days"] == [3, 4]

    # A block with only one active day left is not shown as a series.
    one_left = soccer(id="activity-1", days=[0, 1, 2, 3, 4], missed_days=[2], removed_days=[0, 1, 3, 4])
    shell.session.add_block(one_left)
    shell.session.save()
    settle(qapp, shell)
    sheets.editBlock("activity-1", 2)
    assert sheets.form["showScope"] is False
    assert sheets.form["seriesNote"] == ""
    assert [day["value"] for day in sheets.form["days"] if day["on"]] == [2]
