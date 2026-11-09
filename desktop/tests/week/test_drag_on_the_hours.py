"""The one gesture engine, on painted hours: what a press, a move and a release turn into.

These send Qt mouse events, so they prove the rules; the rig (scripts/rig/drive.py) proves the same
gestures with a real pointer on the real window.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

from desktop.native.hours.canvas import EDGE_PX  # noqa: E402
from desktop.native.hours.geometry import Axis, LinearTrack, Span  # noqa: E402
from desktop.native.hours.hand import Create, Gesture, Held, Move, Place, Verdict, span_words  # noqa: E402
from desktop.tests.week.support_hand import Rig, occurrence, rig_of  # noqa: E402, F401
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_a_block_moves_by_where_it_was_held_and_into_another_day(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(3, 19 * 60 + 30), release=False)
    assert rig.hand.preview is not None and rig.hand.preview.span == Span(3, 19 * 60, 20 * 60)
    assert rig.canvas.held_words() == "Thu 19:00–20:00 · 1 h", "its new times are written on it"
    assert rig.said == [], "nothing changes before it is let go"
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(3, 19 * 60 + 30), False)
    assert rig.said == [Move("essay", 2, Span(3, 19 * 60, 20 * 60))]
    assert rig.hand.preview is None


def test_the_edges_resize_and_never_to_less_than_a_quarter_hour(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    rig.drag(rig.at(2, 19 * 60, -EDGE_PX // 2), rig.at(2, 19 * 60 + 45, -EDGE_PX // 2))
    rig.drag(rig.at(2, 18 * 60, EDGE_PX // 2 + 1), rig.at(2, 17 * 60 + 30, EDGE_PX // 2 + 1))
    rig.drag(rig.at(2, 18 * 60, EDGE_PX // 2 + 1), rig.at(2, 21 * 60))
    assert rig.said == [
        Move("essay", 2, Span(2, 18 * 60, 19 * 60 + 45)),
        Move("essay", 2, Span(2, 17 * 60 + 30, 19 * 60)),
        Move("essay", 2, Span(2, 18 * 60 + 45, 19 * 60)),
    ]


@pytest.mark.parametrize("step", [5, 15])
def test_a_move_a_resize_and_a_new_block_land_on_the_step_and_never_finer(
    rig_of: Callable[..., Rig], step: int
) -> None:
    """A lesson from 17:37 to 18:22, moved, stretched and drawn beside, a minute further each time for
    half an hour. Whatever the hand moves lands on a multiple of the step; at 5 it reaches the steps
    a quarter-hour snap never does, and a lesson off the step comes onto it."""
    evening = lambda area: [  # noqa: E731
        LinearTrack(
            day, QRectF(area.left() + day * 100, area.top(), 100, area.height()), first=17 * 60, last=21 * 60
        )
        for day in range(7)
    ]
    rig = rig_of(lay_out=evening, step=step)
    rig.canvas.set_week([occurrence("lesson", 2, 17 * 60 + 37, 18 * 60 + 22)])

    def drag(start: QPoint, end: QPoint) -> None:
        # Out past the distance that makes a press a drag, then back to where it is let go.
        rig.send(rig.canvas, QEvent.Type.MouseButtonPress, start, True)
        rig.send(rig.canvas, QEvent.Type.MouseMove, start + QPoint(0, 60), True)
        rig.send(rig.canvas, QEvent.Type.MouseMove, end, True)
        rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, end, False)

    landed: list[int] = []
    for offset in range(1, 31):
        rig.said.clear()
        drag(rig.at(2, 18 * 60), rig.at(2, 18 * 60 + offset))
        drag(rig.at(2, 18 * 60 + 22, -3), rig.at(2, 18 * 60 + 22 + offset, -3))
        drag(rig.at(4, 19 * 60, 1), rig.at(4, 19 * 60 + 15 + offset))
        moved, stretched, drawn = rig.said
        landed += [moved.span.start, stretched.span.end, drawn.span.start, drawn.span.end]
    assert [minute for minute in landed if minute % step] == []
    assert {minute % 15 for minute in landed} == ({0, 5, 10} if step == 5 else {0})


def test_dragging_free_time_creates_that_span_and_a_click_makes_up_to_an_hour(
    rig_of: Callable[..., Rig],
) -> None:
    rig = rig_of()
    rig.drag(rig.at(5, 10 * 60, 2), rig.at(5, 11 * 60 + 30))
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, rig.at(2, 17 * 60 + 30, 2), True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(2, 17 * 60 + 30, 2), False)
    assert rig.said == [Create(Span(5, 10 * 60, 11 * 60 + 30)), Create(Span(2, 17 * 60 + 30, 18 * 60))], (
        "the click stops where the essay starts"
    )


def test_a_refused_drop_says_why_and_changes_nothing(rig_of: Callable[..., Rig]) -> None:
    judge = lambda block_id, from_day, span: (  # noqa: E731
        Verdict(False, "That ends after it is due, so it stayed where it was.")
        if span.day > 3
        else Verdict(True, span_words(span))
    )
    rig = rig_of(judge=judge)
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(4, 18 * 60 + 30), release=False)
    assert rig.canvas.held_words() == "That ends after it is due, so it stayed where it was."
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(4, 18 * 60 + 30), False)
    assert rig.said == [("refused", "That ends after it is due, so it stayed where it was.")]


def test_escape_lets_go_without_moving_anything(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(2, 20 * 60), release=False)
    QTest.keyClick(rig.canvas, Qt.Key.Key_Escape)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(2, 20 * 60), False)
    assert rig.said == [] and rig.hand.preview is None and not rig.hand.busy


def test_homework_from_a_tray_is_placed_where_it_is_let_go(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    chip = rig.chip
    start = chip.mapToGlobal(chip.rect().center())
    held = Held(Gesture.PLACE, "Math worksheet", 45, "math")
    rig.send(chip, QEvent.Type.MouseButtonPress, start, True)
    rig.hand.press(chip, held, start)
    for step in range(1, 9):
        rig.send(chip, QEvent.Type.MouseMove, start + (rig.at(4, 17 * 60) - start) * step / 8, True)
    assert rig.canvas.held_words() == "Fri 17:00–17:45 · 45 min"
    rig.send(chip, QEvent.Type.MouseButtonRelease, rig.at(4, 17 * 60), False)
    assert rig.said == [Place("math", Span(4, 17 * 60, 17 * 60 + 45))]


def test_homework_carried_off_the_hours_shows_nowhere_and_places_nothing(rig_of: Callable[..., Rig]) -> None:
    rig = rig_of()
    chip = rig.chip
    start = chip.mapToGlobal(chip.rect().center())
    rig.send(chip, QEvent.Type.MouseButtonPress, start, True)
    rig.hand.press(chip, Held(Gesture.PLACE, "Math worksheet", 45, "math"), start)
    for step in range(1, 9):
        rig.send(chip, QEvent.Type.MouseMove, start + (rig.at(4, 17 * 60) - start) * step / 8, True)
    assert rig.canvas.held_words() == "Fri 17:00–17:45 · 45 min"
    rig.send(chip, QEvent.Type.MouseMove, start, True)
    assert rig.hand.preview is None and rig.canvas.held_words() == ""
    rig.send(chip, QEvent.Type.MouseButtonRelease, start, False)
    assert rig.said == []


def test_a_card_laid_at_an_angle_takes_the_time_along_the_card(rig_of: Callable[..., Rig]) -> None:
    turned = lambda area: [  # noqa: E731
        LinearTrack(
            day,
            QRectF(area.left() + 40 + day * 95, area.top() + 40, 85, 560),
            Axis.DOWN,
            turn=(day - 3) * 5,
        )
        for day in range(7)
    ]
    rig = rig_of(lay_out=turned, height=660)
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(3, 20 * 60 + 30))
    assert rig.said == [Move("essay", 2, Span(3, 20 * 60, 21 * 60))]


def test_an_edge_held_a_few_pixels_in_does_not_jump_on_the_first_move(rig_of: Callable[..., Rig]) -> None:
    """On a 24-hour week where an hour has full edges, six pixels is a dozen minutes or so. Pressed
    six pixels inside the end, the end still moves by exactly what the pointer moves, rather than
    first snapping back."""
    rig = rig_of(height=800)
    per_minute = rig.canvas.tracks[0].per_minute()
    assert 10 <= 6 / per_minute <= 14, "six pixels is about twelve minutes at this scale"
    press = rig.at(2, 19 * 60, -6)
    rig.drag(press, press + QPoint(0, round(30 * per_minute)))
    assert rig.said == [Move("essay", 2, Span(2, 18 * 60, 19 * 60 + 30))]


def test_the_words_that_follow_the_pointer_stay_inside_the_window(rig_of: Callable[..., Rig]) -> None:
    """Carried to the window's right-hand edge, long words were cut off past its side."""
    rig = rig_of()
    title = "Science poster on the water cycle, with the diagrams Ms Alvarez asked for"
    start = rig.chip.mapToGlobal(rig.chip.rect().center())
    corner = rig.chip.mapToGlobal(QPoint(rig.chip.width() - 3, rig.chip.height() // 2))
    rig.hand.press(rig.chip, Held(Gesture.PLACE, title, 45, "poster"), start)
    for step in range(1, 9):
        rig.send(rig.chip, QEvent.Type.MouseMove, start + (corner - start) * step / 8, True)
    label = rig.window.findChild(QLabel, "heldChip")
    assert label is not None and label.isVisible() and label.text() == title
    assert rig.window.rect().contains(label.geometry()), f"{label.geometry()} runs past {rig.window.rect()}"
    rig.hand.cancel()
