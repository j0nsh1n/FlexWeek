"""The Widgets Routines sheet: its first heading, the days of each fixed time as a range, and Apply and
Delete shown only once a routine is saved. How the three sheets that share a top line up, and how the
ticks are drawn, are looks: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.widgets import RoutineDialog
from desktop.tests.sheets.support_dialogs import WEEK, shown, soccer, styled
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-widgets-routines-test"])


def test_routines_heading_ranges_and_hidden_apply(qapp: QApplication) -> None:
    parent, _palette = styled(qapp)
    empty = shown(qapp, RoutineDialog(parent, {}, [soccer()], WEEK))
    titles = [label.text() for label in empty.findChildren(QLabel) if label.objectName() == "cardTitle"]
    assert titles[0] == "Make a routine from this week"
    assert empty.findChild(QPushButton, "saveRoutine").text() != titles[0]
    assert empty.findChild(QPushButton, "applyRoutine").isHidden()
    assert empty.findChild(QPushButton, "deleteRoutine").isHidden()
    assert "Mon–Fri" in empty.choices.item(0).text() or "Tue, Thu" in empty.choices.item(0).text()
    free(empty)
    saved = {"r": {"id": "r", "name": "School week", "blocks": [soccer()]}}
    filled_sheet = shown(qapp, RoutineDialog(parent, saved, [soccer()], WEEK))
    assert filled_sheet.findChild(QPushButton, "applyRoutine").isVisibleTo(filled_sheet)
    free(filled_sheet)
    free(parent)
