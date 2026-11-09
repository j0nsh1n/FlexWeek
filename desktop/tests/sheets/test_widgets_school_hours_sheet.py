"""The School hours sheet: its two time boxes are labelled Start and End, above the boxes."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.widgets import SchoolHoursDialog
from desktop.tests.sheets.support_dialogs import shown, styled
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-school-hours-sheet-test"])


def test_school_hours_labels_its_times_start_and_end_with_no_from_between_them(qapp: QApplication) -> None:
    parent, _palette = styled(qapp)
    dialog = shown(qapp, SchoolHoursDialog(parent, None))
    words = [label.text() for label in dialog.findChildren(QLabel) if label.objectName() == "fieldLabel"]
    assert "Start" in words and "End" in words
    from_labels = [label for label in dialog.findChildren(QLabel) if label.text() == "from"]
    assert not any(label.isVisibleTo(dialog) for label in from_labels)
    free(dialog)
    free(parent)
