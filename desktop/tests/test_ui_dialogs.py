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
    return {"id": "school", "title": "School", "kind": "locked", "category": "class",
            "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4], **fields}


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


def test_going_back_keeps_a_day_the_student_had_already_unticked(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school(), occurrence_day=2)
    dialog.days[4].setChecked(False)
    dialog.scope_occurrence.setChecked(True)
    dialog.scope_series.setChecked(True)
    dialog.accept()
    assert dialog.block()["days"] == [0, 1, 2, 3]
