"""The pictures of the Add / Edit homework form, Add fixed time and Running late: what the old tests
checked by measuring pixels, so the reviewer looks at it drawn instead."""

from __future__ import annotations

from desktop.native.widgets import BlockDialog, HomeworkDialog, LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen

SOURCES = ("desktop/native/widgets.py",)


def _homework(window: NativeWindow, assignment: dict | None = None) -> HomeworkDialog:
    dialog = HomeworkDialog(window, assignment, window.session.today_iso())
    dialog.show()
    return dialog


def _essay(window: NativeWindow) -> dict:
    return {
        "id": "essay",
        "title": "History essay",
        "due": window.session.today_iso(),
        "estimate_min": 60,
        "category": "assignments",
        "revision": 0,
    }


def _length_hint(window: NativeWindow) -> HomeworkDialog:
    dialog = _homework(window)
    dialog.title.setText("History essay")
    dialog._save.click()
    dialog._save.click()
    dialog.estimate.setValue(50)
    dialog.estimate.editingFinished.emit()
    return dialog


def _due_row(window: NativeWindow) -> HomeworkDialog:
    dialog = _homework(window)
    dialog.title.setText("History essay")
    dialog._save.click()
    return dialog


def _edit_scrolled(window: NativeWindow) -> HomeworkDialog:
    dialog = _homework(window, _essay(window))
    dialog.more_details.click()
    dialog._scroll.setFixedHeight(160)
    return dialog


def _empty_title(window: NativeWindow) -> HomeworkDialog:
    dialog = _homework(window)
    dialog._save.click()
    return dialog


def _homework_crumbs(window: NativeWindow) -> HomeworkDialog:
    dialog = _homework(window)
    dialog.title.setText("Spanish essay draft")
    dialog._save.click()
    dialog._save.click()
    return dialog


def _fixed_time_crumbs(window: NativeWindow) -> BlockDialog:
    dialog = BlockDialog(window, day=1, start="15:00")
    dialog.show()
    dialog.title.setText("Chess club")
    dialog._save.click()
    dialog._save.click()
    return dialog


def _running_late(window: NativeWindow) -> LateDialog:
    dialog = LateDialog(window, "School")
    dialog.show()
    return dialog


SCREENS: list[Screen] = [
    Screen(
        id="sheets.homework_length_hint",
        area="sheets",
        prepare=_length_hint,
        checks=(
            "Add homework, third question, with 50 minutes typed: the grey hint under Estimated time is "
            "in the error colour, and its last line never has one word alone on it (the old test tried "
            "every hint width from 140 to 416 px)."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.homework_due_row",
        area="sheets",
        prepare=_due_row,
        checks=(
            "Add homework, second question: the Due by switch sits 1 px further below the date than the "
            "usual gap between two fields of the form."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.homework_edit_scrolled",
        area="sheets",
        prepare=_edit_scrolled,
        checks=(
            "Edit homework with More details open in a body only 160 px tall, so the scroll bar shows: "
            "the fields end exactly 16 px before the scroll bar's handle, and the bar does not overlap "
            "them."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.homework_empty_title",
        area="sheets",
        prepare=_empty_title,
        checks=(
            "Add homework after Next with no title: 'Give the homework a title.' shows on its own row "
            "below the Title field (its top no more than 4 px above the field's bottom edge), wholly "
            "inside the part of the sheet that is visible, at 1920 x 1080 and at 1024 x 640 with Large "
            "text."
        ),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="sheets.homework_step_crumbs",
        area="sheets",
        prepare=_homework_crumbs,
        checks=(
            "Add homework on its last question: the three step names (check What, check When, 3 How "
            "long) show whole in their boxes, with no separator marks between them, at Small, Normal "
            "and Large text and in a sans, a serif and a monospace font."
        ),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="sheets.fixed_time_step_crumbs",
        area="sheets",
        prepare=_fixed_time_crumbs,
        checks=(
            "Add fixed time on its last question: the three step names (check What, check When, 3 "
            "Category) show whole in their boxes, with no separator marks between them, at Small, "
            "Normal and Large text and in a sans, a serif and a monospace font; on a 360 px wide sheet "
            "'check What' and 'check When' are not cut off."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.running_late_buttons",
        area="sheets",
        prepare=_running_late,
        checks=(
            "Running late: Preview, Accept and Cancel sit on one row, side by side, with the same top "
            "edge, in one button box."
        ),
        sources=SOURCES,
    ),
]
