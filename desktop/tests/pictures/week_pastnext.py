"""Screens for the empty week, the empty weekend, the Agenda rail and the Running late preview."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from backend.tests.fake_clock import CLOCK
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


def _empty_week_card(window: NativeWindow) -> QWidget:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window.findChild(QAbstractButton, "viewWeek").click()
    QApplication.processEvents()
    card = window.empty_week
    # The copy-last row is the one the card must be tall enough for.
    card.set_blank(True)
    card.set_over_hours(True)
    card.heading.setWordWrap(True)
    card.line.setWordWrap(True)
    QApplication.processEvents()
    return card


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


def _rail(window: NativeWindow) -> QWidget:
    CLOCK.set(CLOCK.now().replace(hour=15, minute=40))
    session = window.session
    friday = date.fromisoformat(session.week_start) + timedelta(days=4)
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
            "id": "rail-work",
            "title": LONG,
            "due": f"{friday.isoformat()}T23:59",
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    _saved(window)
    block = next(item["id"] for item in session.blocks if item.get("assignment_id") == "rail-work")
    session.hand_move(block, -1, 3, 16 * 60, 17 * 60)
    session.save()
    _saved(window)
    window.resize(1280, 860)
    window.findChild(QAbstractButton, "viewWeek").click()
    QApplication.processEvents()
    return window.rail


def _late_preview(window: NativeWindow) -> QWidget:
    from desktop.native.widgets import LateDialog

    dialog = LateDialog(window, "School")
    long_title = "A very long homework title that cannot fit on one line of the preview list " * 2
    dialog.show()
    dialog.show_trace(
        {
            "moves": [
                {"block_id": "essay", "from_day": 3, "from_start": "19:00", "to_day": 3, "to_start": "19:30"},
                {
                    "block_id": "poster",
                    "from_day": None,
                    "from_start": None,
                    "to_day": 4,
                    "to_start": "15:30",
                },
                {"block_id": "sheet", "from_day": None, "from_start": None, "to_day": 4, "to_start": "14:30"},
            ],
            "placed": [
                {"id": "essay", "title": long_title, "duration_min": 60},
                {"id": "poster", "title": "Science poster", "duration_min": 60},
                {"id": "sheet", "title": "Math worksheet", "duration_min": 60},
            ],
            "unplaced": [],
        },
        {"essay": long_title, "poster": "Science poster", "sheet": "Math worksheet"},
    )
    QApplication.processEvents()
    return dialog


SCREENS: list[Screen] = [
    Screen(
        id="week.empty-week-card",
        area="week",
        prepare=_empty_week_card,
        checks=(
            "the empty-week card is tall enough for its heading, its wrapped line and the copy-last "
            "row, with nothing cut off, at Large text in High contrast (not a fixed 200 px box)"
        ),
        sources=("desktop/native/layouts/empty.py",),
        main=True,
    ),
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
            sources=("desktop/native/layouts", "desktop/native/hours"),
        )
        for design in ("retro", "bento", "timeline")
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
            sources=("desktop/native/layouts", "desktop/native/hours"),
        )
        for design in ("retro", "bento", "timeline")
    ],
    Screen(
        id="week.agenda-rail-long-title",
        area="week",
        prepare=_rail,
        checks=(
            "the Agenda rail is 260 px wide and nothing in it runs past its edge: the body fits the "
            "scroll area, Start focus and each due day stay whole inside the rail, a long homework "
            "title ends in an ellipsis, and the Next rows wrap whole beside a fully visible Start focus"
        ),
        sources=("desktop/native/hours/rail.py", "desktop/native/layouts"),
        main=True,
    ),
    Screen(
        id="week.running-late-preview",
        area="week",
        prepare=_late_preview,
        checks=(
            "each change row's text is drawn once, not also under its row widget; a row with a very "
            "long title is as tall as its wrapped words and taller than a one-line row; Preview and "
            "the accept button share one left edge"
        ),
        sources=("desktop/native/widgets.py",),
    ),
]
