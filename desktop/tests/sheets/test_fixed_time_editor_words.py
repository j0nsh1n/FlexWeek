"""The fixed-time editor as a student reads it.

It is called "fixed time", not "fixed commitment". Ticking another day says it makes the block repeat.
Its buttons carry words and no pictures, Save is the answer Enter gives, and the repeat choices say
only what is true for the day or the series that was opened. Where each button sits and how it is
filled are pictures: desktop/tests/pictures/screens_sheets_h8.py (sheets.fixed-time-editor-answers).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QLabel,
    QProxyStyle,
    QPushButton,
    QStyle,
    QWidget,
)

from desktop.native.widgets import AppStyle, BlockDialog
from desktop.tests.sheets.support_clock_typing import show_and_focus
from desktop.tests.sheets.support_fixed_time import go_when
from desktop.tests.sheets.support_soccer import soccer
from desktop.tests.window_support import free, host, qapp  # noqa: F401


class WantsIcons(QProxyStyle):
    """KDE's style, as far as dialog buttons go: it asks for a floppy disk on Save."""

    def styleHint(self, hint, option=None, widget=None, data=None):  # noqa: N802
        if hint == QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons:
            return 1
        return super().styleHint(hint, option, widget, data)


@pytest.fixture()
def icon_style(qapp: QApplication) -> Iterator[None]:  # noqa: F811
    # The app's own style is a proxy with no name to restore it by.
    ours = isinstance(qapp.style(), AppStyle)
    name = qapp.style().name()
    qapp.setStyle(WantsIcons(name))
    yield
    qapp.setStyle(AppStyle() if ours else name)


def test_the_editor_is_titled_as_a_student_says_it(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    assert BlockDialog(host, day=3, start="17:15").windowTitle() == "Add fixed time"
    assert BlockDialog(host, soccer()).windowTitle() == "Edit fixed time"


def test_it_says_that_ticking_another_day_repeats_it(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    dialog = BlockDialog(host, day=3, start="17:15", duration_min=30, from_range=True)
    dialog.show()
    go_when(dialog)
    note = dialog.findChild(QLabel, "blockRepeatNote")
    assert note.text() == "Pick more days to repeat it."
    assert note.isVisibleTo(dialog)
    series = BlockDialog(host, soccer(), occurrence_day=3)
    series.show()
    series.scope_occurrence.setChecked(True)
    note = series.findChild(QLabel, "blockRepeatNote")
    assert not note.isVisibleTo(series), "the days cannot be changed for this day only"


def test_the_missed_box_names_the_day(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    dialog = BlockDialog(host, soccer(), occurrence_day=3)
    assert dialog.missed.text() == "I missed it on Thursday"


def test_no_button_in_the_editor_has_an_icon(
    qapp: QApplication,  # noqa: F811
    icon_style: None,
    host: QWidget,  # noqa: F811
) -> None:
    dialog = BlockDialog(host, soccer(), occurrence_day=3)
    buttons = dialog.findChildren(QPushButton)
    assert {button.text() for button in buttons} >= {"Save", "Cancel", "Delete"}
    # The close button in the corner is Lucide's x on purpose; a button with words carries none.
    assert [button.text() for button in buttons if button.text() and not button.icon().isNull()] == []


def test_save_is_the_answer_enter_gives_and_delete_is_not_one_of_the_dialogs_answers(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    dialog = BlockDialog(host, soccer(), occurrence_day=3)
    dialog.show()
    qapp.processEvents()
    box = dialog.findChild(QDialogButtonBox)
    save = next(button for button in box.buttons() if button.text() == "Save")
    delete = dialog.findChild(QPushButton, "deleteBlock")
    assert delete not in box.buttons(), "Delete is not one of the dialog's answers"
    assert save.isDefault()


def test_a_series_opened_on_one_day_does_not_also_say_every_day_changes(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    one_day = BlockDialog(host, soccer(), occurrence_day=3)
    one_day.show()
    assert one_day.findChild(QWidget, "editScope").isVisibleTo(one_day)
    note = one_day.findChild(QLabel, "seriesScope")
    assert not note.isVisibleTo(one_day), "it stood over This day only and said the opposite"
    whole = BlockDialog(host, soccer())
    whole.show()
    assert not whole.findChild(QWidget, "editScope").isVisibleTo(whole)
    assert whole.findChild(QLabel, "seriesScope").isVisibleTo(whole)


def test_adding_a_fixed_time_has_what_when_and_category_steps_and_the_third_asks_for_the_category(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    """The third step is Category and its prompt is "What category is it?", not "How long"."""
    block = BlockDialog(host, occurrence_day=3)
    show_and_focus(qapp, block)
    assert [block.findChild(QPushButton, f"blockCrumb{index}").text() for index in range(3)] == [
        "1 What",
        "2 When",
        "3 Category",
    ]
    block.title.setText("Club")
    block._save.click()
    qapp.processEvents()
    block._save.click()
    qapp.processEvents()
    assert block.step_prompt.text() == "What category is it?"
    assert block.category.isVisibleTo(block)
    assert not block.duration_line.isVisibleTo(block)
    free(block)
