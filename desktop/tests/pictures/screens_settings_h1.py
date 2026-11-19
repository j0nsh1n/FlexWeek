"""The pictures of how a look draws the week's blocks: what the code checks of these were pixels, colours
and positions, and are judged on the picture now (spec.md, Testing structure, rule 6)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 405,
    "days": [0],
}
CLUB = {"id": "club", "title": "Club", "kind": "locked", "start": "10:00", "duration_min": 30, "days": [1]}


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


def _settled(window: NativeWindow) -> None:
    wait_until(_app(), lambda: not window.session.busy and not window.session.dirty)




SCREENS: list[Screen] = [
]
