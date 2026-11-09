"""The countdown ring the focus screen and One thing's Countdown share (decision 19 of 0.17): the
share of the arc, the colour it is told to draw in, and the words it reads aloud. What it looks like
(the arc on the track, the number and unit, the scale, the long number, the lines inside) are the
pictures focus.timer_ready, focus.timer_running, focus.countdown_ring_long_number and
focus.countdown_ring_scale (desktop/tests/pictures/_focus_g05.py)."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.look import resolved_palette
    from desktop.native.ring import CountdownRing, RingColours, arc_angles, ring_colours

ARC, TRACK, NUMBER, MUTED = "#ff0000", "#00ff00", "#0000ff", "#ff00ff"
TOP = 90 * 16


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-ring-test"])


def made(qapp: QApplication) -> CountdownRing:
    ring = CountdownRing()
    ring.set_colours(RingColours(ARC, TRACK, NUMBER, MUTED))
    return ring


def test_the_arc_is_the_time_left_from_the_top_clockwise() -> None:
    # Qt's angles are sixteenths of a degree, counted anticlockwise from three o'clock: the arc starts
    # at twelve and a negative span runs clockwise.
    assert arc_angles(0.25) == (TOP, -90 * 16)
    assert arc_angles(0.5) == (TOP, -180 * 16)
    assert arc_angles(1.0) == (TOP, -360 * 16), "all left: the whole ring"
    assert arc_angles(0.0) == (TOP, 0), "none left: no arc"


def test_the_share_left_is_kept_between_none_and_all(qapp: QApplication) -> None:
    assert arc_angles(1.5) == arc_angles(1.0)
    assert arc_angles(-0.5) == arc_angles(0.0)
    ring = made(qapp)
    ring.set_left(20 / 60)
    assert ring.left() == pytest.approx(20 / 60)
    ring.set_left(1.5)
    assert ring.left() == 1.0
    ring.set_left(-1.0)
    assert ring.left() == 0.0


def test_a_timer_not_started_draws_its_arc_in_the_accent_itself(qapp: QApplication) -> None:
    """0.17.0 drew a waiting arc softer, between the track and the accent, so it would not read as done.
    That arc measured 2.1:1 on the page, under the 3:1 a graphic needs, so mockup 6 option A (0.18.3)
    draws it in the accent before Start as after; test_focus_screen checks 3:1 in every look."""
    ring = made(qapp)
    ring.set_left(1.0)
    ring.set_waiting(True)
    assert ring.arc_colour() == ARC, "waiting, it is the accent"
    ring.set_waiting(False)
    assert ring.arc_colour() == ARC, "started, it is the accent"


def test_the_number_and_its_unit_are_read_aloud_together(qapp: QApplication) -> None:
    ring = made(qapp)
    ring.set_number("20", "min")
    assert ring.number() == "20"
    assert ring.accessibleName() == "20 min"
    ring.set_number("20")
    assert ring.accessibleName() == "20"


def test_the_scale_is_the_marks_and_labels_it_was_given(qapp: QApplication) -> None:
    ring = made(qapp)
    assert ring.scale() == (0, ())
    ring.set_scale(12, ("0", "15", "30", "45"))
    assert ring.scale() == (12, ("0", "15", "30", "45"))


def test_the_ring_takes_the_accent_and_a_track_from_the_look() -> None:
    light = resolved_palette("light-frost", False, None)
    colours = ring_colours(light)
    assert (colours.arc, colours.number, colours.muted) == (light["accent"], light["text"], light["muted"])
    assert colours.track not in {light["window"], light["text"], light["accent"]}
    contrast = resolved_palette("system", False, {"preset": "high-contrast", "knobs": {}})
    assert ring_colours(contrast).arc == contrast["accent"]
