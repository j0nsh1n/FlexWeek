"""Screens for the empty week, the empty weekend, the Agenda rail and the Running late preview."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

LONG = "A very long assignment title that must fit the narrow Agenda rail"


def _saved(window: NativeWindow) -> None:
    session = window.session
    wait_until(None, lambda: not session.busy and not session.dirty)


def _show_week(window: NativeWindow, main: str) -> None:
    window._layout = {"main": main, "day": "one", "options": {}}
    window.findChild(QAbstractButton, "viewWeek").click()
    window._on_week()
    QApplication.processEvents()




def _weekend(design: str, with_saturday: bool):
    def prepare(window: NativeWindow) -> None:
        session = window.session
        window.resize(810, 700)
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
        session.add_block(
            {
                "id": "history",
                "title": "History essay",
                "kind": "locked",
                "category": "extra",
                "start": "16:00",
                "duration_min": 60,
                "days": [0, 2, 4],
            }
        )
        if with_saturday:
            session.add_block(
                {
                    "id": "match",
                    "title": "Match",
                    "kind": "locked",
                    "category": "exercise",
                    "start": "10:00",
                    "duration_min": 90,
                    "days": [5],
                }
            )
        session.save()
        _saved(window)
        _show_week(window, design)

    return prepare




SCREENS: list[Screen] = [
    *[
        Screen(
            id=f"week.empty-weekend-{design}",
            area="week",
            prepare=_weekend(design, False),
            checks=(
                "at a narrow window (about 810 px) an empty Saturday and Sunday are narrower than a "
                "weekday, about the same width as each other, and still wide enough to read their "
                "header; the weekdays share one width"
            ),
            sources=("desktop/native/hours",),
        )
        for design in ("classic",)
    ],
    *[
        Screen(
            id=f"week.weekend-with-an-event-{design}",
            area="week",
            prepare=_weekend(design, True),
            checks=(
                "at a narrow window (about 810 px) a Saturday with an event keeps a full weekday-wide "
                "column, while the empty Sunday beside it is narrower"
            ),
            sources=("desktop/native/hours",),
        )
        for design in ("classic",)
    ],
]
