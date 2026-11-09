"""Add fixed time is three questions, same grammar as Add homework: What is the title, When is days plus
Start and End, and the third step is Category (the field it actually asks), not How long. Edit fixed
time stays one page. The Duration line does not say the end moved until the start has changed."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.weekmodel import clock_text, set_clock_24h
from desktop.native.widgets import BlockDialog, HomeworkDialog, StepCrumb
from desktop.tests.window_support import free, host, qapp  # noqa: F401


def opened(parent: QWidget) -> BlockDialog:
    dialog = BlockDialog(parent, day=3, start="17:00")
    dialog.show()
    QApplication.processEvents()
    return dialog


def crumbs(dialog: BlockDialog) -> list[str]:
    return [dialog.findChild(QPushButton, f"blockCrumb{index}").text() for index in range(3)]


def test_add_fixed_time_opens_on_what_and_hides_days_and_duration(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    dialog = opened(host)
    assert dialog.windowTitle() == "Add fixed time"
    assert dialog.step_prompt.text() == "What is it?"
    assert crumbs(dialog) == ["1 What", "2 When", "3 Category"]
    assert dialog.title.isVisibleTo(dialog)
    assert not dialog.day_picker.isVisibleTo(dialog)
    assert not dialog.start.isVisibleTo(dialog)
    assert not dialog.duration_line.isVisibleTo(dialog)
    assert not dialog.category.isVisibleTo(dialog)
    assert dialog._save.text() == "Next"
    assert not dialog.back_button.isVisibleTo(dialog)
    free(dialog)


def test_empty_title_on_next_says_give_it_a_title(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    dialog = opened(host)
    dialog.title.clear()
    dialog._save.click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "What is it?"
    assert dialog.title_problem.text() == "Give it a title."
    assert dialog.title_problem.isVisibleTo(dialog)
    free(dialog)


def test_next_shows_when_then_category(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    dialog = opened(host)
    dialog.title.setText("Club")
    dialog._save.click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "When is it?"
    assert crumbs(dialog)[0] == "✓ What"
    assert dialog.findChild(QPushButton, "blockCrumb0").toolTip() == "Club"
    assert dialog.day_picker.isVisibleTo(dialog)
    assert dialog.start.isVisibleTo(dialog)
    assert dialog.end.isVisibleTo(dialog)
    assert dialog.duration_line.isVisibleTo(dialog)
    assert not dialog.category.isVisibleTo(dialog)
    assert dialog.back_button.text() == "Back"
    assert dialog._save.text() == "Next"
    dialog._save.click()
    QApplication.processEvents()
    assert dialog.step_prompt.text() == "What category is it?"
    assert crumbs(dialog) == ["✓ What", "✓ When", "3 Category"]
    assert dialog.findChild(QPushButton, "blockCrumb1").toolTip() == "Thu, 17:00"
    assert not dialog.duration_line.isVisibleTo(dialog)
    assert dialog.category.isVisibleTo(dialog)
    assert dialog._save.text() == "Save"
    assert not dialog.start.isVisibleTo(dialog)
    free(dialog)


def test_edit_fixed_time_stays_one_page(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    soccer = {
        "id": "soccer",
        "title": "Soccer practice",
        "kind": "locked",
        "category": "sport",
        "start": "16:00",
        "duration_min": 90,
        "days": [1, 3],
    }
    dialog = BlockDialog(host, soccer)
    dialog.show()
    QApplication.processEvents()
    assert dialog.windowTitle() == "Edit fixed time"
    assert dialog.findChild(QWidget, "blockSteps") is None
    assert dialog.title.isVisibleTo(dialog)
    assert dialog.day_picker.isVisibleTo(dialog)
    assert dialog.start.isVisibleTo(dialog)
    assert dialog.duration_line.isVisibleTo(dialog)
    assert dialog.category.isVisibleTo(dialog)
    assert dialog._save.text() == "Save"
    free(dialog)


def test_a_done_fixed_time_crumb_names_its_step_and_gives_the_answer_as_a_tooltip(
    qapp: QApplication,  # noqa: F811
) -> None:
    set_clock_24h(False)
    dialog = BlockDialog(None, day=1, start="15:00", duration_min=60)
    dialog.show()
    dialog.title.setText("Chess club")
    dialog._add_primary()
    dialog._add_primary()
    title_crumb = dialog.findChild(StepCrumb, "blockCrumb0")
    when_crumb = dialog.findChild(StepCrumb, "blockCrumb1")
    assert title_crumb is not None and when_crumb is not None
    assert title_crumb.text() == "✓ What"
    assert title_crumb.toolTip() == "Chess club"
    assert when_crumb.text() == "✓ When"
    assert clock_text(15 * 60) in when_crumb.toolTip()
    free(dialog)


@pytest.mark.parametrize("form", ["homework", "fixed"])
def test_step_crumbs_keep_their_names_and_tick_off_as_the_questions_are_answered(
    qapp: QApplication,  # noqa: F811
    form: str,
) -> None:
    parent = QWidget()
    parent.show()
    if form == "homework":
        dialog = HomeworkDialog(parent, today="2026-10-13")
        dialog.title.setText("Spanish essay draft")
        names = ("What", "When", "How long")
    else:
        dialog = BlockDialog(parent, day=1, start="15:00")
        dialog.title.setText("Chess club")
        names = ("What", "When", "Category")
    dialog.show()
    for step in range(3):
        if step:
            dialog._save.click()
            qapp.processEvents()
        expected = [
            f"✓ {name}" if index < step else f"{index + 1} {name}" for index, name in enumerate(names)
        ]
        assert [crumb.text() for crumb in dialog._crumbs] == expected
    assert not dialog.step_bar.findChildren(QLabel), "the crumb row has no separator marks"
    free(dialog)
    free(parent)


def test_add_fixed_time_does_not_say_end_moved_before_start_changes(qapp: QApplication) -> None:  # noqa: F811
    dialog = BlockDialog(None, day=1, start="16:00", duration_min=60)
    dialog.show()
    dialog.title.setText("Chess club")
    dialog._add_primary()
    dialog._apply_add_step()
    assert dialog._add_step == 1
    assert "End moved" not in dialog.duration_line.text()
    dialog.start.setTime(QTime(16, 30))
    QTest.keyClick(dialog.start, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert "End moved" in dialog.duration_line.text()
    free(dialog)
