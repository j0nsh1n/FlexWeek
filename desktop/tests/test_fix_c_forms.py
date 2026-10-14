"""Lane fix-c (forms and dialogs): crumbs, homework title errors, fixed-time duration line, plan sheet,
restore sheet, running-late buttons."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt, QTime, QTimer
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.settings import RestoreDialog
from desktop.native.weekmodel import clock_text, set_clock_24h
from desktop.native.widgets import BlockDialog, ConfirmSheet, HomeworkDialog, LateDialog, StepCrumb
from desktop.tests.test_dialogs_look import shown, styled
from desktop.tests.window_support import free, qapp, server, signed_out, window  # noqa: F401

pytestmark = pytest.mark.usefixtures("server")


def _block_when(dialog: BlockDialog) -> None:
    dialog.title.setText("Chess club")
    dialog._add_primary()
    dialog._apply_add_step()


def test_fixed_time_crumbs_keep_step_names_and_answer_as_tooltip(qapp) -> None:  # noqa: F811
    set_clock_24h(False)
    host = shown(qapp, BlockDialog(None, day=1, start="15:00", duration_min=60))
    host.resize(360, 640)
    host.title.setText("Chess club")
    host._add_primary()
    host._add_primary()
    title_crumb = host.findChild(StepCrumb, "blockCrumb0")
    when_crumb = host.findChild(StepCrumb, "blockCrumb1")
    assert title_crumb is not None and when_crumb is not None
    assert title_crumb.text() == "✓ What"
    assert title_crumb.toolTip() == "Chess club"
    assert when_crumb.text() == "✓ When"
    assert clock_text(15 * 60) in when_crumb.toolTip()
    for crumb in (title_crumb, when_crumb):
        assert crumb.fontMetrics().horizontalAdvance(crumb.text()) <= crumb.contentsRect().width()
    free(host)


def test_step_crumbs_keep_names_and_fit_for_each_text_size_and_font(qapp) -> None:  # noqa: F811
    for form in ("homework", "fixed"):
        for scale, family in ((0.85, "Sans Serif"), (1.0, "Serif"), (1.2, "Monospace")):
            parent = QWidget()
            parent.resize(1280, 800)
            parent.show()
            dialog = (
                HomeworkDialog(parent, today="2026-10-13")
                if form == "homework"
                else BlockDialog(parent, day=1, start="15:00")
            )
            shown(qapp, dialog)
            crumbs = dialog._crumbs
            names = ("What", "When", "How long" if form == "homework" else "Category")
            font = QFont(crumbs[0].font())
            font.setFamily(family)
            font.setPointSizeF(font.pointSizeF() * scale)
            for crumb in crumbs:
                crumb.setFont(font)
            if form == "homework":
                dialog.title.setText("Spanish essay draft")
            else:
                dialog.title.setText("Chess club")
            for step in range(3):
                if step:
                    dialog._save.click()
                    qapp.processEvents()
                expected = [
                    f"✓ {name}" if index < step else f"{index + 1} {name}"
                    for index, name in enumerate(names)
                ]
                assert [crumb.text() for crumb in crumbs] == expected
                for crumb in crumbs:
                    need = crumb.fontMetrics().horizontalAdvance(crumb.text())
                    assert need <= crumb.contentsRect().width(), (
                        form, scale, family, crumb.text(), crumb.width()
                    )
            assert not dialog.step_bar.findChildren(QLabel), "the crumb row has no separator marks"
            free(dialog)
            free(parent)


@pytest.mark.parametrize(
    ("size", "text_size"),
    [((1920, 1080), "normal"), ((1024, 640), "large")],
)
def test_empty_homework_title_problem_stays_inside_visible_sheet(
    qapp, size: tuple[int, int], text_size: str  # noqa: F811
) -> None:  # noqa: F811
    parent, _ = styled(qapp, text=text_size)
    parent.resize(*size)
    qapp.processEvents()
    dialog = shown(qapp, HomeworkDialog(parent, today="2026-10-13"))
    dialog._save.click()
    qapp.processEvents()
    viewport = dialog._scroll.viewport()
    problem = dialog.title_problem
    point = problem.mapTo(viewport, QPoint(0, 0))
    visible = viewport.rect().contains(problem.rect().translated(point))
    assert problem.text() == "Give the homework a title."
    assert problem.isVisible() and visible, (size, text_size, problem.geometry(), viewport.size())
    free(dialog)
    free(parent)


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
