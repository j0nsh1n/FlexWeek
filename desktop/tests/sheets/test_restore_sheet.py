"""The Restore sheet remembers which restore point was chosen, for Preview and for Restore."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.settings import RestoreDialog


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-restore-sheet-test"])


def test_restore_preview_keeps_the_chosen_point(qapp: QApplication) -> None:
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
