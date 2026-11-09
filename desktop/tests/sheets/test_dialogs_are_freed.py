"""A dialog is freed once it has closed and is let go, and one deleted before its refit runs raises
nothing."""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.widgets import Dialog
from desktop.tests.sheets.support_dialogs import _dialog_classes, school


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-dialogs-freed-test"])


def test_every_dialog_is_freed_once_it_has_closed_and_is_let_go(qapp: QApplication) -> None:
    """PySide gives an exec()'d dialog to Python, to be freed with its last reference. A button
    wired to a lambda that named the dialog kept that reference inside Qt, where the garbage
    collector cannot reach it, so the dialog outlived its use. At quit PySide then deleted it and the
    window it belongs to one after the other, and FlexWeek crashed on the way out: "shared QObject
    was deleted directly", then a bus error."""
    import gc
    import weakref
    from unittest.mock import Mock

    from desktop.native import devices, look_editor, settings, widgets

    homework = {"id": "essay", "title": "Essay", "due": "2026-09-27T23:59", "estimate_min": 60, "revision": 0}
    pasted = {
        "block": school(id="copy", days=[2], start="16:00", duration_min=60),
        "day": 2,
        "fixed": True,
        "checked": True,
    }
    sync = Mock(spec=devices.SyncService)
    sync.pair_start.return_value = None
    made = {
        devices.PairDialog: [lambda host: devices.PairDialog(host, sync, 1)],
        devices.RemoveDialog: [lambda host: devices.RemoveDialog(host, "Pixel")],
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
        widgets.BlockDialog: [lambda host: widgets.BlockDialog(host, school(), occurrence_day=1)],
        widgets.HomeworkDialog: [
            lambda host: widgets.HomeworkDialog(host, homework, "2026-09-21", waiting=True, pinned=True),
            lambda host: widgets.HomeworkDialog(host, None, "2026-09-21"),
        ],
        widgets.PreviewDialog: [lambda host: widgets.PreviewDialog(host, "Paste", "", [pasted], [school()])],
        widgets.ChooseTimeDialog: [
            lambda host: widgets.ChooseTimeDialog(
                host, {**homework, "duration_min": 60, "days": [1]}, "2026-09-21", [1, 2], [school()], None, 1
            )
        ],
        widgets.RoutineDialog: [lambda host: widgets.RoutineDialog(host, {}, [school()], "2026-09-21")],
        widgets.LateDialog: [lambda host: widgets.LateDialog(host, "School")],
        widgets.SpreadDialog: [
            lambda host: widgets.SpreadDialog(host, {**homework, "unplanned_min": 120}, "2026-09-21")
        ],
        widgets.AvailabilityDialog: [lambda host: widgets.AvailabilityDialog(host, {}, ["Math"])],
        widgets.SchoolHoursDialog: [
            lambda host: widgets.SchoolHoursDialog(host, school()),
            lambda host: widgets.SchoolHoursDialog(host, None),
        ],
        settings.RestoreDialog: [lambda host: settings.RestoreDialog(host, [], None, None)],
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
    assert set(made) == _dialog_classes(), "a dialog is missing here: add a way to make it"
    host = QWidget()
    host.show()
    kept = []
    for kind, makers in made.items():
        for make in makers:
            dialog = make(host)
            QTimer.singleShot(0, dialog.reject)
            dialog.exec()
            gone = weakref.ref(dialog)
            del dialog
            gc.collect()
            if gone() is not None:
                kept.append(kind.__name__)
                gone().deleteLater()
                qapp.processEvents()
    host.deleteLater()
    assert kept == [], f"still alive after closing and being let go: {kept}"


def test_a_dialog_deleted_before_its_refit_runs_raises_nothing(qapp: QApplication) -> None:
    """refit() asks for the resize on the next turn of the event loop; a dialog deleted before that
    turn used to be called on, and the error only reached sys.excepthook."""
    raised: list[BaseException] = []
    previous, sys.excepthook = sys.excepthook, lambda _kind, error, _trace: raised.append(error)
    try:
        dialog = Dialog()
        dialog.refit()
        dialog.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        # The turns of the event loop the refit was waiting for, counted rather than timed.
        for _ in range(5):
            qapp.processEvents()
    finally:
        sys.excepthook = previous
    assert raised == []
