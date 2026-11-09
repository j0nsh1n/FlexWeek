"""The Study hours sheet: touching and overlapping hours are kept, there is a limit of 21 sets that
hours equal to a saved set never count against, and hours that end before they start are refused."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, QTime
from PySide6.QtWidgets import QApplication

from desktop.native.widgets import AvailabilityDialog


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-study-hours-test"])


def test_touching_and_overlapping_study_hours_are_kept(qapp: QApplication) -> None:
    windows = [
        {"days": [0], "start": "15:00", "end": "17:00"},
        {"days": [0], "start": "17:00", "end": "19:00"},
        {"days": [0], "start": "16:00", "end": "18:00"},
    ]
    dialog = AvailabilityDialog(None, {"work_windows": windows})
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.work_windows() == windows


def test_study_hours_stop_at_the_limit(qapp: QApplication) -> None:
    full = [{"days": [at % 7], "start": f"{at:02d}:00", "end": f"{at:02d}:30"} for at in range(21)]
    dialog = AvailabilityDialog(None, {"work_windows": full})
    dialog._open_picker(kind="study", day=0)
    dialog.picker_start.setTime(QTime(22, 0))
    dialog.picker_end.setTime(QTime(23, 0))
    dialog.picker_add.click()
    assert dialog.error.text() == "Up to 21 sets of study hours."
    assert dialog.work_windows() == full
    # Hours equal to some already saved join them, so they never count against the limit.
    dialog._open_picker(kind="study", day=1)
    dialog.picker_start.setTime(QTime(0, 0))
    dialog.picker_end.setTime(QTime(0, 30))
    dialog.picker_add.click()
    assert dialog.error.text() == ""
    assert dialog.work_windows()[0] == {"days": [0, 1], "start": "00:00", "end": "00:30"}


def test_study_hours_that_end_before_they_start_are_refused(qapp: QApplication) -> None:
    dialog = AvailabilityDialog(None, {"work_windows": [{"days": [5, 6], "start": "10:00", "end": "12:00"}]})
    dialog._open_picker(kind="study", day=5)
    dialog.picker_start.setTime(QTime(10, 0))
    dialog.picker_end.setTime(QTime(9, 45))
    dialog.picker_add.click()
    assert dialog.error.text() == "End needs to be later than Start (10:00)."
    assert dialog.picker.isVisibleTo(dialog), "the picker stays open to fix the time"
    dialog.picker_cancel.click()
    assert dialog.error.text() == ""
    assert dialog.work_windows() == [{"days": [5, 6], "start": "10:00", "end": "12:00"}]
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
