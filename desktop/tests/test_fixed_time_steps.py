"""Add fixed time as three questions, same grammar as Add homework pick C.

The HTML demo's `fixed()` has no C branch. What is the title, When is days plus Start and End, and
the third step is Category (the field it actually asks), not How long. Edit event stays one page.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.widgets import BlockDialog
from desktop.tests.window_support import free, host, qapp  # noqa: F401


def opened(parent: QWidget) -> BlockDialog:
    dialog = BlockDialog(parent, day=3, start="17:00")
    dialog.show()
    QApplication.processEvents()
    return dialog


def go_when(dialog: BlockDialog) -> None:
    if dialog._add_step is None or dialog._add_step >= 1:
        return
    if not dialog.title.text().strip():
        dialog.title.setText("Club")
    dialog._save.click()
    QApplication.processEvents()


def go_length(dialog: BlockDialog) -> None:
    go_when(dialog)
    if dialog._add_step is None or dialog._add_step >= 2:
        return
    dialog._save.click()
    QApplication.processEvents()


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


def test_edit_event_stays_one_page(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
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
