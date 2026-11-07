"""Screens of the planner area's Undo notice: Plan's Undo toast, and the toast over Bento's footer.

The lead merges SCREENS into screens_planner.py. Each `prepare` puts the light window in the state and
never asserts; the checks are what the code tests used to measure with numbers."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled

WEDNESDAY = 2
EVENT_PASSES = 20


def _essay_due_sunday(window: NativeWindow) -> None:
    """History essay, one hour, due Sunday, with the clock held on Wednesday 14:07 of the open week."""
    session = window.session
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
    settled(None, window)
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=WEDNESDAY, hours=14, minutes=7))
    window._fill_classic()
    for _ in range(EVENT_PASSES):
        QApplication.processEvents()


def _after_plan(window: NativeWindow) -> None:
    """The classic week with the essay placed by Plan and the Undo toast up."""
    window._layout = sanitize_layout({"main": "classic", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    _essay_due_sunday(window)
    solve = window.findChild(QPushButton, "solveButton")
    if solve is None:
        solve = window.solve_button
    solve.click()
    wait_until(
        None,
        lambda: window.toast.isVisible() and window.toast.button.isVisible(),
        what="Plan's Undo toast",
    )
    settled(None, window)
    for _ in range(EVENT_PASSES):
        QApplication.processEvents()


def _bento_with_unplaced_homework(window: NativeWindow) -> None:
    """Bento's week with one homework that has no time, so its Not placed yet tile shows "Drag one onto the
    week.", and the notice "Moved History essay to Fri 18:00." with Undo up over the page's foot."""
    window._layout = sanitize_layout({"main": "bento", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    session = window.session
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
    settled(None, window)
    window._on_week()
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", lambda: None)
    for _ in range(EVENT_PASSES):
        QApplication.processEvents()


def _bento_footer_scrolled_to_the_bottom(window: NativeWindow) -> None:
    _bento_with_unplaced_homework(window)
    scroll = window.findChild(QScrollArea, "bentoScroll")
    if scroll is not None:
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
    for _ in range(EVENT_PASSES):
        QApplication.processEvents()


SCREENS: list[Screen] = [
    Screen(
        id="planner.undo_toast_after_plan",
        area="planner",
        prepare=_after_plan,
        checks=(
            "Plan's Undo toast sits bottom right, with the words 'Placed 1 homework block.' and an Undo"
            " button reading 'Undo · N s'. The thin progress line along the toast's foot is the action"
            " colour at 60% opacity and as long as the time left. The Undo button keeps one width as the"
            " seconds tick down (12 s to 1 s), so the words beside it never lose room."
        ),
        sources=(
            "desktop/native/widgets.py",
            "desktop/native/window.py",
        ),
        main=True,
    ),
    Screen(
        id="planner.undo_toast_over_bento_footer",
        area="planner",
        prepare=_bento_with_unplaced_homework,
        checks=(
            "In Bento, the settled Undo toast ('Moved History essay to Fri 18:00.') does not cover the"
            " 'Drag one onto the week.' instruction in the Not placed yet tile, or any other footer text:"
            " the instruction's text sits clearly above the toast card, with the toast's top edge below"
            " the text's bottom edge. This holds at 1280x800, 1280x820 and 1024x740, and at Large text."
        ),
        sources=(
            "desktop/native/widgets.py",
            "desktop/native/layouts/bento.py",
        ),
        main=True,
    ),
    Screen(
        id="planner.undo_toast_over_bento_footer_scrolled",
        area="planner",
        prepare=_bento_footer_scrolled_to_the_bottom,
        checks=(
            "In Bento at the cramped 1024x740 size, with the page scrolled all the way down, no visible"
            " label text in the page runs under the Undo toast's card: the last tile's words end above the"
            " card, or the card sits where no text is."
        ),
        sources=(
            "desktop/native/widgets.py",
            "desktop/native/layouts/bento.py",
        ),
    ),
]
