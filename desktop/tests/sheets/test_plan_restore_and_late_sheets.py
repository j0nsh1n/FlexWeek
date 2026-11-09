"""Three sheets that open from the window: Before planning (a confirm sheet for unfinished homework),
Restore points, and Running late, whose Preview gives way to Accept once a preview is shown."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.settings import RestoreDialog
from desktop.native.widgets import ConfirmSheet, LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import free, qapp  # noqa: F401


def test_before_planning_asks_on_a_confirm_sheet(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    items = [{"id": "carry", "title": "Essay", "left_over_state": "carried"}]
    window._unfinished_items = lambda: items  # type: ignore[method-assign]
    seen: list[str] = []

    def read() -> None:
        sheet = QApplication.activeModalWidget()
        if isinstance(sheet, ConfirmSheet):
            seen.append(sheet.findChild(QLabel, "sheetTitle").text())
            sheet.reject()

    QTimer.singleShot(0, read)
    window._plan_with_left_over()
    assert seen == ["Before planning"]


def test_restore_points_opens_as_a_sheet(qapp: QApplication) -> None:  # noqa: F811
    dialog = RestoreDialog(None, [], None, None)
    dialog.show()
    assert dialog.findChild(QLabel, "sheetTitle").text() == "Restore points"
    assert dialog.findChild(QPushButton, "sheetClose") is not None
    free(dialog)


def test_running_late_hides_preview_and_shows_accept_once_a_preview_is_shown(qapp: QApplication) -> None:  # noqa: F811
    parent = QLabel()
    parent.show()
    late = LateDialog(parent, "School")
    late.show()
    preview = late.findChild(QPushButton, "latePreview")
    assert preview.isVisible()
    late.show_trace({"moves": [], "unplaced": []}, {})
    qapp.processEvents()
    assert not preview.isVisible()
    assert late.accept_button.isVisible()
    free(late)
    free(parent)
