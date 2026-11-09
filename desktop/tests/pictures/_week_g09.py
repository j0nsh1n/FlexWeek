"""Week pictures from the views lane's group G09: Clay in the smallest window, and the marks and words on
Clay's and Mission's blocks in every look. The lead gathers this fragment into screens_week.py."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import CATEGORIES
from desktop.native.layouts.registry import DESIGN_LOOKS, sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

CLAY = ("desktop/native/layouts/clay.py", "desktop/native/window.py", "desktop/native/hours")
PAINTERS = (
    "desktop/native/layouts/clay.py",
    "desktop/native/layouts/mission.py",
    "desktop/native/hours/canvas.py",
    "desktop/native/look.py",
)


def _saved(window: NativeWindow) -> None:
    session = window.session
    wait_until(
        QApplication.instance(),
        lambda: not session.busy and not session.dirty and not getattr(session.client, "pending", 0),
        what="the window to finish saving",
    )


def _spin(rounds: int = 20) -> None:
    for _ in range(rounds):
        QApplication.processEvents()


def _show(window: NativeWindow, main: str, looks: dict | None = None) -> None:
    options = {main: looks} if looks else {}
    window._layout = sanitize_layout({"main": main, "day": "one", "options": options})
    window._apply_appearance()
    window._on_week()
    _spin()


def _clay_small(day_mode: bool, front: int | None):
    """Clay with homework left over from last week (the planning strip above the deck takes its room, as
    it does for a student with work behind) and a Morning class on every day."""

    def prepare(window: NativeWindow) -> None:
        session = window.session
        monday = datetime.fromisoformat(session.week_start)
        due = (monday - timedelta(days=3)).strftime("%Y-%m-%dT23:59")
        left = {"id": "left", "title": "Lab report", "due": due, "estimate_min": 60, "revision": 0}
        session.add_homework(left)
        session.add_block(
            {
                "id": "edge-class",
                "title": "Morning class",
                "kind": "locked",
                "category": "class",
                "start": "08:00",
                "duration_min": 90,
                "days": list(range(7)),
            }
        )
        session.save()
        _saved(window)
        session.set_view("day" if day_mode else "week")
        _show(window, "clay", None)
        if front is not None:
            window.planner.currentWidget().row._go(front, "jump", force=True)
            _spin()

    return prepare


def _blocks_of_every_category(main: str, look: str):
    """One block of every kind of time on its own day, in `main` worn in `look`."""

    def prepare(window: NativeWindow) -> None:
        session = window.session
        for day, (category, spec) in enumerate(CATEGORIES.items()):
            if category == "assignments":
                session.add_homework(
                    {
                        "id": "homework-mark",
                        "title": "Homework",
                        "due": (datetime.fromisoformat(session.week_start) + timedelta(days=6)).strftime(
                            "%Y-%m-%dT23:59"
                        ),
                        "estimate_min": 60,
                        "revision": 0,
                    }
                )
                continue
            session.add_block(
                {
                    "id": f"mark-{category}",
                    "title": spec["label"],
                    "kind": "locked",
                    "category": category,
                    "start": "10:00" if day < 7 else "14:00",
                    "duration_min": 60,
                    "days": [day % 7],
                }
            )
        session.save()
        _saved(window)
        placed = next(
            block for block in session.blocks if block.get("assignment_id") == "homework-mark"
        )
        session.add_block({**placed, "start": "10:00", "days": [1]})
        session.save()
        _saved(window)
        _show(window, main, {"look": look})

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="week.clay_small_window",
        area="week",
        prepare=_clay_small(day_mode=False, front=None),
        checks=(
            "Clay's week at the smallest window the app is meant for (1024 x 640) with Large text and "
            "homework left over from last week. The card in front is whole on the screen: its top is not "
            "above the page's viewport and its bottom is not cut by it (the row once asked for 340 px of "
            "height at any text size, so the page scrolled and the bottom of the card was cut). The "
            "Morning class block on the front card's hours is whole or scrolled clear past, never cut "
            "by the hour list's or the page's edge. The window keeps 1024 x 640: Clay does not make it "
            "grow, and the hidden sign-in page does not raise its minimum."
        ),
        sources=CLAY,
        main=True,
    ),
    Screen(
        id="week.clay_small_window_day_mode",
        area="week",
        prepare=_clay_small(day_mode=True, front=None),
        checks=(
            "The same smallest window with Clay showing one day: the front card is whole on the screen "
            "and the Morning class block on its hours is whole or scrolled clear past, never cut."
        ),
        sources=CLAY,
        main=True,
    ),
    Screen(
        id="week.clay_small_window_last_day",
        area="week",
        prepare=_clay_small(day_mode=False, front=6),
        checks=(
            "The same smallest window with Sunday brought to the front of Clay's deck (the old test "
            "tried all seven days): the card is whole on the screen and the Morning class block is "
            "whole or scrolled clear past."
        ),
        sources=CLAY,
        main=True,
    ),
]


def _slug(token: str) -> str:
    return token.replace(":", "_").replace("-", "_")


for _design, _name in (("clay", "Clay"), ("mission", "Mission")):
    for _token in (*(value for value, _label in DESIGN_LOOKS[_design]), "your"):
        SCREENS.append(
            Screen(
                id=f"week.{_design}_block_words_{_slug(_token)}",
                area="week",
                prepare=_blocks_of_every_category(_design, _token),
                checks=(
                    f"{_name} worn in the look {_token}: each block's title and time read on its own "
                    "colour, whatever its kind of time (School, Homework, Study, Sports, Extra, Meals, "
                    "Sleep, Free). The words keep at least 4.5 to 1 against the block, in the light and "
                    "dark pack, and the mark is pale on a light card and sunk into a dark one. "
                    "Regressions seen: Clay lightened each mark and Mission darkened it, so in Match "
                    "my look homework's darker mark came out neon red under dark words and Mission's "
                    "blocks were ink under ink."
                ),
                sources=PAINTERS,
            )
        )
