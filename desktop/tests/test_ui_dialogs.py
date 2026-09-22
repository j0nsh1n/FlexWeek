"""Dialogs read the way the window reads them: after exec() has returned and the dialog is hidden.

Each test here is a control that looked as if it worked and did nothing, or did something else.
Expected behaviour comes from the web editor (frontend/editor.js) where the web has the same control.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.widgets import BlockDialog


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-dialog-test"])
    yield application


def school(**fields: object) -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "category": "class",
        "start": "08:00",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        **fields,
    }


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


def ticked(dialog: BlockDialog) -> list[int]:
    return [index for index, check in enumerate(dialog.days) if check.isChecked()]


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


def test_restore_preview_keeps_the_chosen_point(qapp: QApplication) -> None:
    from desktop.native.settings import RestoreDialog

    points = [{"id": "p1", "label": "Before", "created_at": "2026-09-18", "weeks_count": 1}]
    preview = {"id": "p1", "changes": {"weeks": {}, "assignments": {}}}
    first = RestoreDialog(None, points, None, None)
    first.show()
    qapp.processEvents()
    first.list.setCurrentRow(0)
    first._preview()
    assert first.selected_id == "p1"
    reopened = RestoreDialog(None, points, preview, None)
    reopened.show()
    qapp.processEvents()
    reopened._restore()
    assert reopened.selected_id == "p1"


def test_going_back_keeps_a_day_the_student_had_already_unticked(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school(), occurrence_day=2)
    dialog.days[4].setChecked(False)
    dialog.scope_occurrence.setChecked(True)
    dialog.scope_series.setChecked(True)
    dialog.accept()
    assert dialog.block()["days"] == [0, 1, 2, 3]


TRACK = "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"


def test_a_fixed_commitment_keeps_the_spotify_link_that_was_typed(qapp: QApplication) -> None:
    """The Spotify button already opened a block's link, but nothing here could put one there."""
    dialog = BlockDialog(None, school())
    dialog.spotify.setText(TRACK)
    dialog.accept()
    assert dialog.block()["spotify_url"] == TRACK


def test_an_existing_link_is_shown_so_it_can_be_changed_or_cleared(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school(spotify_url=TRACK))
    assert dialog.spotify.text() == TRACK
    dialog.spotify.clear()
    dialog.accept()
    assert dialog.block()["spotify_url"] is None


def test_a_link_that_is_not_spotify_is_refused_with_a_message(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school())
    dialog.spotify.setText("https://example.com/rickroll")
    dialog.accept()
    assert dialog.isVisible() is False  # never shown, so it cannot be visible either way
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "spotify" in dialog.error.text().lower()


def test_homework_keeps_its_spotify_link_too(qapp: QApplication) -> None:
    from desktop.native.widgets import HomeworkDialog

    dialog = HomeworkDialog(None, None, "2026-09-14")
    dialog.title.setText("Essay")
    dialog.spotify.setText(TRACK)
    dialog.accept()
    assert dialog.assignment()["spotify_url"] == TRACK


def test_the_homework_editor_is_wide_enough_to_read_after_it_was_made_to_scroll(
    qapp: QApplication,
) -> None:
    """A scroll area reports its own width, not its content's, so the dialog came up too narrow to
    read the fields until a minimum was set."""
    from desktop.native.widgets import HomeworkDialog

    dialog = HomeworkDialog(None, None, "2026-09-14")
    dialog.show()
    qapp.processEvents()
    dialog.adjustSize()
    qapp.processEvents()
    assert dialog.width() >= 500
    assert dialog.height() >= 400
    dialog.close()


def test_an_off_grid_estimate_says_to_use_a_multiple_of_fifteen(qapp: QApplication) -> None:
    from desktop.native.widgets import ESTIMATE_ERROR, SLOT_HINT, HomeworkDialog

    dialog = HomeworkDialog(None, None, "2026-09-14")
    dialog.title.setText("Essay")
    dialog.estimate.setValue(20)
    dialog.show()
    qapp.processEvents()
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert dialog.error.text() == ESTIMATE_ERROR
    assert dialog.error.isVisible()
    assert dialog.findChild(type(dialog.estimate_hint), "homeworkEstimateHint").text() == SLOT_HINT
    dialog.close()


def test_homework_optional_fields_sit_behind_more_details(qapp: QApplication) -> None:
    from desktop.native.widgets import HomeworkDialog

    blank = HomeworkDialog(None, None, "2026-09-14")
    blank.show()
    qapp.processEvents()
    assert blank.findChild(type(blank.more_details), "homeworkMoreDetails") is not None
    assert blank._details.isVisible() is False
    blank.more_details.setChecked(True)
    assert blank._details.isVisible() is True
    blank.close()

    filled = HomeworkDialog(
        None,
        {
            "id": "math",
            "title": "Math worksheet",
            "due": "2026-09-14T21:00",
            "estimate_min": 45,
            "revision": 0,
            "course": "Math",
            "notes": "",
            "links": [],
            "checklist": [],
        },
        "2026-09-14",
    )
    filled.show()
    qapp.processEvents()
    assert filled.more_details.isChecked() is True
    assert filled._details.isVisible() is True
    filled.close()


def test_a_fixed_activity_is_a_start_and_an_end_with_the_length_worked_out(qapp: QApplication) -> None:
    """School is 08:00 to 14:30, not 390 minutes. An editable Duration beside End was a second way to
    say the same thing, and the two could disagree."""
    from PySide6.QtCore import QTime
    from PySide6.QtWidgets import QAbstractSpinBox

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
    from PySide6.QtCore import QTime

    dialog = BlockDialog(None, school())
    dialog.show()
    qapp.processEvents()
    dialog.end.setTime(QTime(7, 30))
    qapp.processEvents()
    assert dialog.duration_line.text() == "End must be after Start."
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    # Said once, beside the times, as an error; not repeated at the bottom of the form.
    assert dialog.duration_line.property("problem") is True
    assert dialog.error.text() == ""
    dialog.end.setTime(QTime(15, 10))
    qapp.processEvents()
    assert dialog.duration_line.text() == "Use quarter hours, such as 15:00 or 15:15."
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    dialog.close()


def test_a_bad_username_is_named(qapp: QApplication) -> None:
    from desktop.native.client import USERNAME_ERROR, _error

    err = _error(
        422,
        [
            {
                "type": "string_too_short",
                "loc": ["body", "username"],
                "msg": "String should have at least 3 characters",
                "input": "x",
            }
        ],
    )
    assert err.message == USERNAME_ERROR
    generic = _error(422, [{"type": "value_error", "loc": ["body", "title"], "msg": "title required"}])
    assert "required fields" in generic.message


def test_a_short_password_names_the_field_instead_of_a_generic_check(qapp: QApplication) -> None:
    from desktop.native.client import PASSWORD_LENGTH_HINT, _error

    err = _error(
        422,
        [
            {
                "type": "string_too_short",
                "loc": ["body", "password"],
                "msg": "String should have at least 12 characters",
                "input": "x",
            }
        ],
    )
    assert err.message == PASSWORD_LENGTH_HINT
    generic = _error(422, [{"type": "value_error", "loc": ["body", "title"], "msg": "title required"}])
    assert "required fields" in generic.message
    assert "x" not in err.message
