"""What the Material screens in desktop/tests/pictures/_*_g12.py share: Material on screen and the
School-and-History-essay week the sheet tests use. Nothing here asserts; a screen that cannot be put in
its state is reported by the renderer."""

from __future__ import annotations

import contextlib

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump, show_material
from desktop.tests.waiting import wait_until


def material(window: NativeWindow) -> QObject:
    """The Material root, with the week on screen."""
    return show_material(QApplication.instance(), window)


def settle(window: NativeWindow) -> None:
    """Wait for the session to finish saving; a timeout is left for the picture to show."""
    with contextlib.suppress(AssertionError):
        wait_until(
            QApplication.instance(),
            lambda: not window.session.busy and not window.session.dirty,
            what="the session to finish saving",
        )
    pump(QApplication.instance(), 10)


def seed_school_and_essay(window: NativeWindow) -> None:
    """School Monday to Friday 08:00 to 14:30, and the History essay due Sunday, planned Thursday 18:45."""
    session = window.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settle(window)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    settle(window)


def add_block(
    window: NativeWindow, key: str, title: str, category: str, start: str, minutes: int, days: list[int]
) -> None:
    window.session.add_block(
        {
            "id": key,
            "title": title,
            "kind": "locked",
            "category": category,
            "start": start,
            "duration_min": minutes,
            "days": days,
        }
    )


def add_homework(window: NativeWindow, key: str, title: str, due: str, minutes: int) -> None:
    window.session.add_homework(
        {"id": key, "title": title, "due": due, "estimate_min": minutes, "revision": 0}
    )
