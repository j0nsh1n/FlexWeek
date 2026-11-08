"""Opening every dialog with sample data, and reading which of its buttons are painted filled. The dialog
button tests and the filled-button screens share these; test_sheets_0183 imports `filled`."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QPushButton, QWidget

from desktop.native import devices, look_editor, settings, widgets

HOMEWORK = {"id": "essay", "title": "Essay", "due": "2026-09-27T23:59", "estimate_min": 60, "revision": 0}
RESTORE_POINT = {"id": "a", "label": "Monday", "weeks_count": 2}


def school(**fields: object) -> dict:
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "category": "class",
        "start": "08:00",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        **fields,
    }


ROUTINE = {"weekdays": {"id": "weekdays", "name": "School weeks", "blocks": [school()]}}


def dialog_classes() -> set[type]:
    """Every dialog class the app defines."""
    import desktop.native.window  # noqa: F401 - brings in every module that defines a dialog

    found, waiting = set(), [QDialog]
    while waiting:
        for kind in waiting.pop().__subclasses__():
            waiting.append(kind)
            if kind.__module__.startswith("desktop.native."):
                found.add(kind)
    return found


def makers() -> dict[type, list[Callable[[QWidget], QDialog]]]:
    """For each dialog class, the ways to open it on sample data, given the widget to open it on."""
    pasted = {
        "block": school(id="copy", days=[2], start="16:00", duration_min=60),
        "day": 2,
        "fixed": True,
        "checked": True,
    }
    windows = {"work_windows": [{"days": [0, 1], "start": "16:00", "end": "18:00"}]}
    sync = Mock(spec=devices.SyncService)
    sync.pair_start.return_value = None
    sync.pair_status.return_value = {"state": "idle", "expires_at_ms": 0, "tries_left": 0}
    return {
        widgets.BlockDialog: [
            lambda host: widgets.BlockDialog(host, school(), occurrence_day=1),
            lambda host: widgets.BlockDialog(host, None),
        ],
        widgets.HomeworkDialog: [
            lambda host: widgets.HomeworkDialog(host, HOMEWORK, "2026-09-21", waiting=True, pinned=True),
            lambda host: widgets.HomeworkDialog(host, None, "2026-09-21"),
        ],
        widgets.PreviewDialog: [lambda host: widgets.PreviewDialog(host, "Paste", "", [pasted], [school()])],
        widgets.ChooseTimeDialog: [
            lambda host: widgets.ChooseTimeDialog(
                host, {**HOMEWORK, "duration_min": 60, "days": [1]}, "2026-09-21", [1, 2], [school()], None, 1
            )
        ],
        widgets.RoutineDialog: [
            lambda host: widgets.RoutineDialog(host, {}, [school()], "2026-09-21"),
            lambda host: widgets.RoutineDialog(host, ROUTINE, [school()], "2026-09-21"),
        ],
        widgets.LateDialog: [lambda host: widgets.LateDialog(host, "School")],
        widgets.SpreadDialog: [
            lambda host: widgets.SpreadDialog(host, {**HOMEWORK, "unplanned_min": 120}, "2026-09-21")
        ],
        widgets.AvailabilityDialog: [lambda host: widgets.AvailabilityDialog(host, windows, ["Math"])],
        widgets.SchoolHoursDialog: [
            lambda host: widgets.SchoolHoursDialog(host, school()),
            lambda host: widgets.SchoolHoursDialog(host, None),
        ],
        widgets.Dialog: [lambda host: widgets.Dialog(host)],
        widgets.ConfirmSheet: [
            lambda host: widgets.ConfirmSheet(
                host,
                "Sign out",
                "Sure?",
                (("stay", "Cancel", "outlined"), ("yes", "Sign out", "")),
                default="stay",
            )
        ],
        look_editor.ColourSheet: [lambda host: look_editor.ColourSheet(host, "#3d6fc4")],
        look_editor.StartSheet: [lambda host: look_editor.StartSheet(host, "base:light", [])],
        devices.PairDialog: [lambda host: devices.PairDialog(host, sync, 1)],
        devices.RemoveDialog: [lambda host: devices.RemoveDialog(host, "Pixel")],
        settings.RestoreDialog: [
            lambda host: settings.RestoreDialog(host, [RESTORE_POINT], None, None)
        ],
        settings.AccountDialog: [lambda host: settings.AccountDialog(host, 3, {"username": "student"})],
        settings.AlarmRingDialog: [
            lambda host: settings.AlarmRingDialog(host, {"name": "Wake up", "time": "06:45"}, "")
        ],
        settings.TransferPreviewDialog: [lambda host: settings.TransferPreviewDialog(host, {})],
        settings.AboutDialog: [lambda host: settings.AboutDialog(host, {"mode": "local"}, "FlexWeek")],
        settings.HelpDialog: [lambda host: settings.HelpDialog(host)],
        settings.UpdateDialog: [
            lambda host: settings.UpdateDialog(host, {"version": "9.9.9", "notes": "", "url": ""}, "0.13.0")
        ],
    }


def filled(dialog: QDialog, accent: str) -> list[str]:
    """The buttons on screen painted in the accent, read from a picture of each."""
    shown = []
    for button in dialog.findChildren(QPushButton):
        if not button.isVisibleTo(dialog) or button.width() < 8:
            continue
        # A ticked day is a choice shown, like a segment, not a second thing to press.
        if button.isCheckable() and (button.property("pill") or button.objectName() == "setupChip"):
            continue
        # Most of it in the accent. One pixel near the left edge could land on a link's accent words,
        # "Skip this version", depending on the font, and called it filled.
        image = button.grab().toImage()
        wanted = QColor(accent)
        points = [(x, y) for x in range(0, image.width(), 3) for y in range(0, image.height(), 3)]
        inked = sum(1 for x, y in points if image.pixelColor(x, y) == wanted)
        if inked > len(points) / 2:
            shown.append(button.text() or button.objectName())
    return shown
