"""The Widgets Add fixed time and Edit fixed time sheet: which rows show, what the start and end work
out, which days an edit keeps, the missed-day box, and the words that refuse a bad entry. Where the
labels and boxes sit and how wide they are, are looks: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, QTime
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QCheckBox, QLabel, QLineEdit, QPushButton

from desktop.native.widgets import BlockDialog, Segmented, day_range_words, guess_locked_category
from desktop.tests.sheets.support_dialogs import school, shown, soccer, styled
from desktop.tests.test_fixed_time_steps import go_length, go_when
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-fixed-time-editor-test"])


def ticked(dialog: BlockDialog) -> list[int]:
    return [index for index, check in enumerate(dialog.days) if check.isChecked()]


def test_ticking_this_day_was_missed_is_still_known_after_the_dialog_closes(qapp: QApplication) -> None:
    """The window asks recover_missed() once exec() returns, when every child reports not visible."""
    dialog = BlockDialog(None, school(), occurrence_day=2)
    dialog.show()
    qapp.processEvents()
    dialog.missed.setChecked(True)
    dialog.accept()
    assert dialog.isVisible() is False
    assert dialog.recover_missed() is True


def test_a_new_block_never_asks_for_a_missed_replan(qapp: QApplication) -> None:
    dialog = BlockDialog(None, day=0, start="16:00")
    dialog.title.setText("Soccer")
    dialog.missed.setChecked(True)
    dialog.accept()
    assert dialog.recover_missed() is False, "the box is not offered for a block that does not exist yet"


def test_unticking_a_missed_day_restores_it(qapp: QApplication) -> None:
    """The web button reads "Restore Wed" and removes that day from missed_days (editor.js)."""
    dialog = BlockDialog(None, school(missed_days=[1, 2]), occurrence_day=2)
    assert dialog.missed.isChecked() is True
    dialog.missed.setChecked(False)
    dialog.accept()
    assert dialog.block()["missed_days"] == [1]
    assert dialog.recover_missed() is False


def test_trying_this_day_only_and_going_back_keeps_the_series_days(qapp: QApplication) -> None:
    """The web leaves the day boxes alone when the scope changes (editor.js, setEditScope).

    Here "This day only" ticked Wednesday alone and going back only re-enabled the boxes, so Save
    took School off Monday, Tuesday, Thursday and Friday.
    """
    dialog = BlockDialog(None, school(), occurrence_day=2)
    dialog.scope_occurrence.setChecked(True)
    assert ticked(dialog) == [2]
    assert not any(check.isEnabled() for check in dialog.days)
    dialog.scope_series.setChecked(True)
    assert ticked(dialog) == [0, 1, 2, 3, 4]
    assert all(check.isEnabled() for check in dialog.days)
    dialog.accept()
    assert dialog.scope() == "series"
    assert dialog.block()["days"] == [0, 1, 2, 3, 4]


def test_going_back_keeps_a_day_the_student_had_already_unticked(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school(), occurrence_day=2)
    # Opened from one day, the editor starts on that day only; the student goes to the series first.
    dialog.scope_series.setChecked(True)
    dialog.days[4].setChecked(False)
    dialog.scope_occurrence.setChecked(True)
    dialog.scope_series.setChecked(True)
    dialog.accept()
    assert dialog.block()["days"] == [0, 1, 2, 3]


def test_the_repeat_scope_is_a_choice_of_two_under_the_days_only_for_a_repeating_block(
    qapp: QApplication,
) -> None:
    parent, _palette = styled(qapp)
    one_day = shown(qapp, BlockDialog(parent, soccer(), occurrence_day=3))
    scope = one_day.findChild(Segmented, "editScope")
    assert scope.isVisibleTo(one_day)
    assert [button.text() for button in scope.buttons()] == ["This day only", "Every Tue and Thu"]
    assert scope.buttons()[0].isChecked(), "This day only is the narrowest default"
    assert one_day.findChildren(QCheckBox, "scopeOccurrence") == [], "no radio buttons over the title"
    scope.buttons()[1].click()
    one_day.days[4].click()
    assert scope.buttons()[1].text() == "Every Tue, Thu and Fri"
    scope.buttons()[0].click()
    assert one_day.scope() == "occurrence"
    for other in (
        BlockDialog(parent, soccer(days=[3]), occurrence_day=3),
        BlockDialog(parent, day=3, start="17:00"),
        BlockDialog(parent, soccer()),
    ):
        shown(qapp, other)
        assert not other.findChild(Segmented, "editScope").isVisibleTo(other)
        free(other)
    free(one_day)
    free(parent)


def test_a_fixed_activity_is_a_start_and_an_end_with_the_length_worked_out(qapp: QApplication) -> None:
    """School is 08:00 to 14:30, not 390 minutes. An editable Duration beside End was a second way to
    say the same thing, and the two could disagree."""
    dialog = BlockDialog(None, school())
    dialog.show()
    qapp.processEvents()
    assert (dialog.start.time().toString("HH:mm"), dialog.end.time().toString("HH:mm")) == ("08:00", "14:30")
    assert dialog.duration_line.text() == "6 h 30 min"
    assert dialog.findChild(QAbstractSpinBox, "blockDuration") is None
    dialog.end.setTime(QTime(15, 0))
    qapp.processEvents()
    assert dialog.duration_line.text() == "7 h"
    dialog.accept()
    assert dialog.block()["duration_min"] == 420
    dialog.close()


def test_a_fixed_activity_that_ends_before_it_starts_is_refused_beside_the_times(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school())
    dialog.show()
    qapp.processEvents()
    dialog.end.setTime(QTime(7, 30))
    qapp.processEvents()
    assert dialog.duration_line.text() == "End needs to be later than Start (08:00)."
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    # Said once, beside the times, as an error; not repeated at the bottom of the form.
    assert dialog.duration_line.property("problem") is True
    assert dialog.error.text() == ""
    dialog.close()


def test_a_fixed_activity_the_editor_cannot_save_is_explained_in_the_apps_words(qapp: QApplication) -> None:
    """The editor checks a block with the server's own rules, and says the problem in the app's words."""
    said = {}
    for field, fill in (("title", "   "), ("days", None)):
        dialog = BlockDialog(None, school())
        if field == "title":
            dialog.title.setText(fill)
        else:
            for check in dialog.days:
                check.setChecked(False)
        dialog.accept()
        assert dialog.result() != dialog.DialogCode.Accepted
        said[field] = dialog.error.text()
        dialog.close()
    assert said == {
        "title": "Give it a title.",
        "days": "Tick at least one day.",
    }


def test_add_fixed_time_is_titled_that_and_guesses_category_from_the_start(qapp: QApplication) -> None:
    """Edit stays Edit event. New event is the old title, renamed."""
    parent, _palette = styled(qapp)
    added = shown(qapp, BlockDialog(parent, day=3, start="10:00"))
    assert added.windowTitle() == "Add fixed time"
    assert added.findChild(QLabel, "sheetTitle").text() == "Add fixed time"
    go_when(added)
    assert added.findChild(QLabel, "blockRepeatNote").text() == "Pick more days to repeat it."
    go_length(added)
    duration = next(label for label in added.findChildren(QLabel) if label.text() == "Duration")
    assert not duration.isVisibleTo(added), "the Category step asks only for Category"
    assert added.category.isVisibleTo(added)
    assert added.category.currentData() == "class"
    added.start.setTime(added.start.time().addSecs(8 * 3600))
    qapp.processEvents()
    # 10:00 + 8 h = 18:00, a meal window.
    assert added.category.currentData() == "meals"
    added.category.setCurrentIndex(added.category.findData("extra"))
    added.start.setTime(added.start.time().addSecs(-6 * 3600))
    qapp.processEvents()
    assert added.category.currentData() == "extra", "a choice the student made is kept"
    assert added.findChild(QLineEdit, "blockSpotify") is None
    assert added.findChild(QPushButton, "blockMoreDetails") is None
    free(added)
    edited = shown(qapp, BlockDialog(parent, soccer(), occurrence_day=3))
    assert edited.windowTitle() == "Edit fixed time"
    assert edited.findChild(QLineEdit, "blockSpotify") is None
    assert edited.findChild(QPushButton, "blockMoreDetails") is None
    free(edited)
    free(parent)


def test_category_guess_follows_school_meals_and_afternoon_activity() -> None:
    assert guess_locked_category("08:00") == "class"
    assert guess_locked_category("07:30") == "meals"
    assert guess_locked_category("12:15") == "meals"
    assert guess_locked_category("18:00") == "meals"
    assert guess_locked_category("16:00") == "extra"
    assert guess_locked_category("21:00") == "extra"


def test_day_ranges_collapse_three_or_more_in_a_row() -> None:
    assert day_range_words([0, 1, 2, 3, 4]) == "Mon–Fri"
    assert day_range_words([0, 2, 4]) == "Mon, Wed, Fri"
    assert day_range_words([0, 1]) == "Mon, Tue"
    assert day_range_words([4, 5, 6]) == "Fri–Sun"
