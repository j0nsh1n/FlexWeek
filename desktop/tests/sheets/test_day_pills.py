"""Days are picked with pills everywhere: the block editor's Add fixed time used check boxes while setup
used pills, so one choice looked two ways."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton, QWidget

from desktop.native.calendar import DAYS
from desktop.native.widgets import BlockDialog
from desktop.tests.window_support import free, host, qapp  # noqa: F401


def day_boxes(root: QWidget) -> list[str]:
    """Check boxes named for a day: what the pills replace."""
    return [box.text() for box in root.findChildren(QCheckBox) if box.text() in DAYS]


def pills(root: QWidget) -> list[QPushButton]:
    return [button for button in root.findChildren(QPushButton) if button.property("pill")]


def test_the_block_editor_picks_its_days_with_pills(qapp: QApplication, host: QWidget) -> None:  # noqa: F811
    block = {"id": "s", "title": "Soccer", "kind": "locked", "start": "16:00", "duration_min": 60}
    dialog = BlockDialog(host, {**block, "days": [1]})
    assert day_boxes(dialog) == []
    shown = pills(dialog)
    assert [pill.text() for pill in shown] == list(DAYS)
    assert [pill.isChecked() for pill in shown] == [day == 1 for day in range(7)]
    shown[3].click()
    dialog.accept()
    assert dialog.block()["days"] == [1, 3]
    free(dialog)


def test_routines_and_school_hours_pick_days_with_pills(
    qapp: QApplication,  # noqa: F811
    host: QWidget,  # noqa: F811
) -> None:
    """(Availability edits each day on its own row since #54, so it has no days to pick.)"""
    from desktop.native.widgets import RoutineDialog, SchoolHoursDialog

    routines = RoutineDialog(host, {}, [], "2026-09-21")
    school = SchoolHoursDialog(host, None)
    for made in (routines, school):
        assert day_boxes(made) == [], type(made).__name__
        assert [pill.text() for pill in pills(made)] == list(DAYS), type(made).__name__
    pills(routines)[6].click()
    assert routines.selected_days() == [0, 1, 2, 3, 4, 5]
    pills(school)[0].click()
    assert school.days.days() == [1, 2, 3, 4]
    for made in (routines, school):
        free(made)




