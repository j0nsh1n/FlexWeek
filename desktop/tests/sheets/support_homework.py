"""Helpers for tests of the Add / Edit homework form: a parent window with a session, the dialog
opened on it, and the steps that take Add homework to its second and third question."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.widgets import HomeworkDialog

TODAY = "2026-09-14"
LATE_EVENING = datetime(2026, 9, 14, 22, 41)
SCHOOL = {
    "id": "school",
    "kind": "locked",
    "category": "class",
    "days": [0, 1, 2, 3, 4],
    "start": "08:00",
    "duration_min": 390,
}


def host(*blocks: dict, now: datetime = LATE_EVENING) -> QWidget:
    """A parent whose session has this week's blocks and a clock, as the window's session does."""
    parent = QWidget()
    parent.session = SimpleNamespace(  # type: ignore[attr-defined]
        now_ms=lambda: int(now.timestamp() * 1000), blocks=list(blocks), week_start=TODAY
    )
    return parent


def session(day: int, start: str | None, **more: object) -> dict:
    return {
        "id": f"s{day}{start}",
        "title": "History essay",
        "kind": "flexible",
        "assignment_id": "essay",
        "duration_min": 60,
        "days": [day],
        **({"start": start} if start else {}),
        **more,
    }


def essay(**more: object) -> dict:
    return {
        "id": "essay",
        "title": "History essay",
        "due": "2026-09-25",
        "estimate_min": 60,
        "category": "assignments",
        "revision": 0,
        **more,
    }


def opened(parent: QWidget, assignment: dict | None = None) -> HomeworkDialog:
    dialog = HomeworkDialog(parent, assignment, TODAY)
    dialog.show()
    QApplication.processEvents()
    return dialog


def go_when(dialog: HomeworkDialog) -> None:
    """Add homework's second question. The demo hides Due until What has a title."""
    if dialog._add_step is None or dialog._add_step >= 1:
        return
    if not dialog.title.text().strip():
        dialog.title.setText("History essay")
    dialog._save.click()
    QApplication.processEvents()


def go_length(dialog: HomeworkDialog) -> None:
    """Add homework's third question. Estimated time is not on the first page."""
    go_when(dialog)
    if dialog._add_step is None or dialog._add_step >= 2:
        return
    dialog._save.click()
    QApplication.processEvents()
