"""Which button in a dialog is the answer: one filled button, and the others outlined or quiet. What is
drawn in the accent is a picture (screens_sheets_h7.py); this file checks how each button is marked and
that every dialog is covered by those pictures."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from desktop.native import settings, widgets
from desktop.tests.sheets.support_buttons import (
    HOMEWORK,
    RESTORE_POINT,
    ROUTINE,
    dialog_classes,
    makers,
    school,
)
from desktop.tests.window_support import qapp  # noqa: F401


def test_every_dialog_has_a_way_to_be_opened_for_the_filled_button_pictures() -> None:
    assert set(makers()) == dialog_classes(), "a dialog is missing here: add a way to make it"


def test_the_filled_button_is_the_answer(qapp: QApplication) -> None:  # noqa: F811
    """The ones that were loud before are outlined (More details) or quiet (Apply, Delete, Close), and the
    answer beside them is still filled."""
    homework = widgets.HomeworkDialog(None, HOMEWORK, "2026-09-21")
    assert homework.more_details.property("outline") is True, "outlined: as words alone it was not seen"
    routines = widgets.RoutineDialog(None, ROUTINE, [school()], "2026-09-21")
    names = {button.objectName(): button for button in routines.findChildren(QPushButton)}
    assert not names["saveRoutine"].property("quiet")
    # Close is the sheet's own x in its corner now, quiet like the rest.
    for name in ("applyRoutine", "deleteRoutine", "sheetClose"):
        assert names[name].property("quiet") is True, name
    late = widgets.LateDialog(None, "School")
    assert not late.findChild(QPushButton, "latePreview").property("outlined")
    assert not late.accept_button.property("quiet")


def test_hide_preview_and_save_restore_point_are_outlined_and_close_stays_plain(
    qapp: QApplication,  # noqa: F811
) -> None:
    """The three bare-text actions are outlined, as Delete beside Hide is; Restore stays the one filled
    button and Close, which only dismisses, stays plain."""
    panel = widgets.UnfinishedPanel(None)
    dialog = settings.RestoreDialog(None, [RESTORE_POINT], None, None)
    close = dialog.findChild(QPushButton, "sheetClose")
    for button in (
        panel.findChild(QPushButton, "unfinishedDismiss"),
        dialog.findChild(QPushButton, "restorePreview"),
        dialog.findChild(QPushButton, "restoreCreate"),
    ):
        assert button.property("outlined") is True and not button.property("quiet"), button.text()
    assert close.property("quiet") is True and not close.property("outlined")
    restore = dialog.findChild(QPushButton, "restoreApply")
    assert not restore.property("quiet") and not restore.property("outlined")


def test_routines_and_running_late_say_what_each_part_is_for(qapp: QApplication) -> None:  # noqa: F811
    """Routines was a list box, an empty box, a date and four filled buttons, and Running late an empty
    box, with nothing saying what either was for. As sheets each part is a heading and a sentence on the
    one card, not a card inside it."""
    routines = widgets.RoutineDialog(None, {}, [school()], "2026-09-21")
    assert routines.findChildren(QFrame, "dialogCard") == [], "no card inside the card"
    titles = [label.text() for label in routines.findChildren(QLabel, "cardTitle")]
    assert titles == ["Make a routine from this week", "Use a saved routine"]
    notes = routines.findChildren(QLabel, "cardNote")
    assert len(notes) == 2 and all(note.text() for note in notes)
    empty = routines.findChild(QLabel, "routineEmpty")
    assert empty.text() == "No routines saved yet." and not empty.isHidden()
    assert routines.list.isHidden(), "no empty box where the routines would be"
    late = widgets.LateDialog(None, "School")
    assert late.findChild(QLabel, "sheetTitle").text() == "Running late"
    assert late.findChild(QLabel, "cardNote").text()
    assert late.changes.isHidden(), "the list of moves shows once there is a preview"
    late.show_trace({"moves": [], "unplaced": []}, {})
    assert not late.changes.isHidden()


class _Session:
    """What the focus panel reads, for a Quick focus that is running or has ended, or no timer."""

    def __init__(self, phase: str | None) -> None:
        self.focus = None if phase is None else {"title": "Quick focus", "phase": phase, "running": True}
        self.assignments: dict = {}

    def now_next_text(self) -> str:
        return ""

    def now_ms(self) -> int:
        return 0

    def focus_tasks(self) -> list:
        return []


@pytest.mark.parametrize(("phase", "answer"), [("work", "Focus screen"), ("ended", "Finished")])
def test_quick_focus_is_a_card_with_one_filled_button(
    qapp: QApplication,  # noqa: F811
    phase: str,
    answer: str,
) -> None:
    panel = settings.FocusPanel()
    panel.set_state(_Session(phase))
    card = panel.findChild(QFrame, "dialogCard")
    assert card.isVisibleTo(panel)
    assert card.findChild(QLabel, "focusTask").text() == "Quick focus"
    assert card.findChild(QLabel, "cardNote").text()
    loud = [
        button.text()
        for button in card.findChildren(QPushButton)
        if button.isVisibleTo(panel) and not button.property("quiet")
    ]
    assert loud == [answer]
    panel.set_state(_Session(None))
    assert not card.isVisibleTo(panel), "no card while no timer runs"
