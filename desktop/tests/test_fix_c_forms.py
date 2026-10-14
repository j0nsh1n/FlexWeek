"""Lane fix-c (forms and dialogs): crumbs, homework title errors, fixed-time duration line, plan sheet,
restore sheet, running-late buttons."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.settings import RestoreDialog
from desktop.native.weekmodel import clock_text, set_clock_24h
from desktop.native.widgets import BlockDialog, ConfirmSheet, HomeworkDialog, LateDialog, StepCrumb
from desktop.tests.window_support import server, signed_out, window  # noqa: F401

pytestmark = pytest.mark.usefixtures("server")
from desktop.tests.test_dialogs_look import shown
from desktop.tests.window_support import free, qapp  # noqa: F401


def _block_when(dialog: BlockDialog) -> None:
    dialog.title.setText("Chess club")
    dialog._add_primary()
    dialog._apply_add_step()


def test_fixed_time_crumbs_use_the_clock_and_elide(qapp) -> None:  # noqa: F811
    set_clock_24h(False)
    host = shown(qapp, BlockDialog(None, day=1, start="15:00", duration_min=60))
    host.resize(360, 640)
    host.title.setText("Chess club with a very long name that should not clip mid-word")
    host._add_primary()
    host._add_primary()
    title_crumb = host.findChild(StepCrumb, "blockCrumb0")
    when_crumb = host.findChild(StepCrumb, "blockCrumb1")
    assert title_crumb is not None and when_crumb is not None
    assert title_crumb.text().endswith("…")
    assert "15:00" not in when_crumb.accessibleName()
    assert clock_text(15 * 60) in when_crumb.accessibleName()
    free(host)


def test_homework_title_problem_has_its_own_row(qapp) -> None:  # noqa: F811
    dialog = shown(qapp, HomeworkDialog(None, today="2026-10-13"))
    dialog._add_primary()
    qapp.processEvents()
    assert dialog.title_problem.isVisible()
    assert dialog.title_problem.text() == "Give the homework a title."
    geo = dialog.title.geometry()
    prob = dialog.title_problem.geometry()
    assert prob.top() > geo.bottom() - 4
    free(dialog)


def test_add_fixed_time_does_not_say_end_moved_before_start_changes(qapp) -> None:  # noqa: F811
    dialog = shown(qapp, BlockDialog(None, day=1, start="16:00", duration_min=60))
    _block_when(dialog)
    assert dialog._add_step == 1
    assert "End moved" not in dialog.duration_line.text()
    dialog.start.setTime(QTime(16, 30))
    QTest.keyClick(dialog.start, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert "End moved" in dialog.duration_line.text()
    free(dialog)


def test_before_planning_uses_a_confirm_sheet(qapp, window) -> None:  # noqa: F811
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
    for _ in range(20):
        qapp.processEvents()
    assert seen == ["Before planning"]


def test_restore_points_opens_as_a_sheet(qapp) -> None:  # noqa: F811
    dialog = shown(qapp, RestoreDialog(None, [], None, None))
    assert dialog.findChild(QLabel, "sheetTitle").text() == "Restore points"
    assert dialog.findChild(QPushButton, "sheetClose") is not None
    free(dialog)


def test_running_late_keeps_preview_and_accept_on_one_row(qapp) -> None:  # noqa: F811
    parent = QLabel()
    parent.show()
    late = shown(qapp, LateDialog(parent, "School"))
    preview = late.findChild(QPushButton, "latePreview")
    accept = late.accept_button
    cancel = next(b for b in late.findChildren(QPushButton) if b.text() == "Cancel")
    assert preview.parentWidget() is accept.parentWidget()
    assert preview.y() == accept.y()
    assert preview.y() == cancel.y()
    late.show_trace({"moves": [], "unplaced": []}, {})
    qapp.processEvents()
    assert not preview.isVisible()
    assert accept.isVisible()
    free(late)
    free(parent)
