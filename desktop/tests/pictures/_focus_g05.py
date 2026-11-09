"""Screens for the countdown ring of the focus timer: what the ring's old pixel tests read back."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.tests.fake_clock import CLOCK
from desktop.tests.pictures.screen import Screen

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow

RING_SOURCES = (
    "desktop/native/ring.py",
    "desktop/native/focus_screen.py",
    "desktop/native/focus.py",
)


def _focus_screen(window: NativeWindow) -> object:
    """The focus timer opened ready, as the Quick focus button does. The Widgets focus screen is
    returned; Material draws its own timer, so for it the whole window is photographed (None)."""
    window._open_focus_screen()
    screen = window.focus_screen
    return screen if window._stack.currentWidget() is screen else None


def _ring_before_start(window: NativeWindow) -> object:
    return _focus_screen(window)


def _ring_running(window: NativeWindow) -> object:
    _focus_screen(window)
    window._start_quick_focus()
    CLOCK.move(minutes=10)
    window.session.tick_focus()
    screen = window.focus_screen
    return screen if window._stack.currentWidget() is screen else None


def _ring_long_number(window: NativeWindow) -> object:
    screen = _focus_screen(window)
    if screen is not None:
        window.focus_screen.ring.set_left(0.5)
        window.focus_screen.ring.set_number("124:59")
    return screen


def _ring_scale_and_lines(window: NativeWindow) -> object:
    screen = _focus_screen(window)
    if screen is not None:
        ring = window.focus_screen.ring
        ring.set_waiting(False)
        ring.set_left(0.5)
        ring.set_number("20", "min")
        ring.set_scale(12, ("0", "15", "30", "45"))
        # Two lines of the owner's over the number, as One thing's Countdown puts its title, and one under.
        window.focus_screen.phase.setText("Soccer practice\nand the drive")
        window.focus_screen.task.setText("16:00–17:30")
        ring.lines_changed()
    return screen


SCREENS: list[Screen] = [
    Screen(
        id="focus.ring_before_start",
        area="focus",
        prepare=_ring_before_start,
        checks=(
            "The focus timer set but not started: the whole ring is the arc, drawn in the accent itself, "
            "not softer than it (a softer arc measured 2.1:1 on the page, under the 3:1 a graphic needs; "
            "it must read 3:1 or more against the page in every look). The track is a soft tint between "
            "the page and the text colour. The arc begins at twelve o'clock. The number is in the middle "
            "of the ring in the text colour, and the lines above and below it sit inside the ring without "
            "touching the track."
        ),
        sources=RING_SOURCES,
    ),
    Screen(
        id="focus.ring_running",
        area="focus",
        prepare=_ring_running,
        checks=(
            "A quick focus of 30 minutes with 10 minutes gone, so 20 of 30 minutes (two thirds) are left. "
            "The arc starts at twelve o'clock and runs clockwise for the share left, so the first two "
            "thirds of the ring (twelve to eight o'clock) are the accent and the last third is the track. "
            "The arc has a round end while part of the ring is left. In the High contrast look the "
            "ring's arc is yellow (#ffd400)."
        ),
        sources=RING_SOURCES,
    ),
    Screen(
        id="focus.ring_long_number",
        area="focus",
        prepare=_ring_long_number,
        checks=(
            "A long number, 124:59, shrinks to stay inside the ring: the ink of the number starts right "
            "of the inner circle's left edge and ends left of its right edge, and it does not touch the "
            "track. It stays in the text colour and is not clipped."
        ),
        sources=RING_SOURCES,
    ),
    Screen(
        id="focus.ring_scale_and_lines",
        area="focus",
        prepare=_ring_scale_and_lines,
        checks=(
            "The ring as One thing's Countdown draws it: 12 marks round the outside of the track in the "
            "muted colour, with 0, 15, 30 and 45 at every third mark, the mark at the top drawn outside "
            "the track. The number 20 is in the middle in the text colour with its unit, min, beside it "
            "in the muted colour. A two-line title over the number and a time line under it keep their "
            "room: the number takes only the height they leave, none of the three touches the others, "
            "and all of them stay inside the ring, not over the track."
        ),
        sources=RING_SOURCES,
    ),
]
