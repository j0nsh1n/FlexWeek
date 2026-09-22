"""The one gesture engine, on painted hours: what a press, a move and a release turn into.

These send Qt mouse events, so they prove the rules; the rig (scripts/rig/drive.py) proves the same
gestures with a real pointer on the real window.
"""

from __future__ import annotations

import importlib.util
import os
import time
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea, QVBoxLayout, QWidget

    from desktop.native.hours.canvas import EDGE_PX, BlockPainter, HoursCanvas
    from desktop.native.hours.geometry import Axis, LinearTrack, Span
    from desktop.native.hours.hand import Create, Gesture, Hand, Held, Move, Place, Verdict, span_words
    from desktop.native.look import resolved_palette
    from desktop.native.weekmodel import Occurrence


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-hand-test"])


def occurrence(block_id: str, day: int, start: int, end: int, work: bool = False) -> Occurrence:
    return Occurrence(
        block_id,
        block_id.title(),
        "homework" if work else "class",
        day,
        start,
        end,
        work,
        False,
        False,
        None,
        None,
        None,
    )


WEEK = [
    *(occurrence("school", day, 8 * 60, 14 * 60 + 30) for day in range(5)),
    occurrence("essay", 2, 18 * 60, 19 * 60, work=True),
]


class Rig:
    """A window with a week of hours, a tray chip and a hand, and what the hand reported."""

    def __init__(self, qapp: QApplication, judge=None, lay_out=None, height: int = 680) -> None:
        self.window = QWidget()
        # Inside the offscreen screen (800 by 800), where QApplication.widgetAt can find it.
        self.window.resize(760, 760)
        box = QVBoxLayout(self.window)
        box.setContentsMargins(0, 0, 0, 0)
        self.chip = QPushButton("Math worksheet")
        box.addWidget(self.chip)
        self.said: list[object] = []
        self.hand = Hand(
            judge or (lambda block_id, from_day, span: Verdict(True, span_words(span))), self.window
        )
        self.hand.committed.connect(self.said.append)
        self.hand.refused.connect(lambda words: self.said.append(("refused", words)))
        self.hand.opened.connect(lambda block_id: self.said.append(("opened", block_id)))
        painter = BlockPainter(resolved_palette("system", False, None))
        self.canvas = HoursCanvas(
            self.hand,
            painter,
            lay_out
            or (
                lambda area: [
                    LinearTrack(day, QRectF(area.left() + day * 100, area.top(), 100, area.height()))
                    for day in range(7)
                ]
            ),
        )
        self.canvas.setFixedHeight(height)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.canvas)
        box.addWidget(self.scroll, 1)
        self.canvas.set_week(WEEK)
        self.window.show()
        qapp.processEvents()
        self.canvas.relayout()

    def at(self, day: int, minute: int, nudge: int = 0) -> QPoint:
        return self.canvas.point_for(day, minute) + QPoint(0, nudge)

    def send(self, widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
        local = QPointF(widget.mapFromGlobal(at))
        buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
        event = QMouseEvent(
            kind, local, QPointF(at), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
        )
        QApplication.sendEvent(widget, event)

    def drag(
        self, start: QPoint, end: QPoint, *, release: bool = True, source: QWidget | None = None
    ) -> None:
        source = source or self.canvas
        self.send(source, QEvent.Type.MouseButtonPress, start, True)
        for step in range(1, 9):
            self.send(source, QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
        if release:
            self.send(source, QEvent.Type.MouseButtonRelease, end, False)


def test_a_block_moves_by_where_it_was_held_and_into_another_day(qapp: QApplication) -> None:
    rig = Rig(qapp)
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(3, 19 * 60 + 30), release=False)
    assert rig.hand.preview is not None and rig.hand.preview.span == Span(3, 19 * 60, 20 * 60)
    assert rig.canvas.held_words() == "Thu 19:00–20:00 · 1 h", "its new times are written on it"
    assert rig.said == [], "nothing changes before it is let go"
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(3, 19 * 60 + 30), False)
    assert rig.said == [Move("essay", 2, Span(3, 19 * 60, 20 * 60))]
    assert rig.hand.preview is None


def test_the_edges_resize_and_never_to_less_than_a_quarter_hour(qapp: QApplication) -> None:
    rig = Rig(qapp)
    rig.drag(rig.at(2, 19 * 60, -EDGE_PX // 2), rig.at(2, 19 * 60 + 45, -EDGE_PX // 2))
    rig.drag(rig.at(2, 18 * 60, EDGE_PX // 2 + 1), rig.at(2, 17 * 60 + 30, EDGE_PX // 2 + 1))
    rig.drag(rig.at(2, 18 * 60, EDGE_PX // 2 + 1), rig.at(2, 21 * 60))
    assert rig.said == [
        Move("essay", 2, Span(2, 18 * 60, 19 * 60 + 45)),
        Move("essay", 2, Span(2, 17 * 60 + 30, 19 * 60)),
        Move("essay", 2, Span(2, 18 * 60 + 45, 19 * 60)),
    ]


def test_dragging_free_time_creates_that_span_and_a_click_makes_up_to_an_hour(qapp: QApplication) -> None:
    rig = Rig(qapp)
    rig.drag(rig.at(5, 10 * 60, 2), rig.at(5, 11 * 60 + 30))
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, rig.at(2, 17 * 60 + 30, 2), True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(2, 17 * 60 + 30, 2), False)
    assert rig.said == [Create(Span(5, 10 * 60, 11 * 60 + 30)), Create(Span(2, 17 * 60 + 30, 18 * 60))], (
        "the click stops where the essay starts"
    )


def test_a_refused_drop_says_why_and_changes_nothing(qapp: QApplication) -> None:
    judge = lambda block_id, from_day, span: (  # noqa: E731
        Verdict(False, "That ends after it is due, so it stayed where it was.")
        if span.day > 3
        else Verdict(True, span_words(span))
    )
    rig = Rig(qapp, judge)
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(4, 18 * 60 + 30), release=False)
    assert rig.canvas.held_words() == "That ends after it is due, so it stayed where it was."
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(4, 18 * 60 + 30), False)
    assert rig.said == [("refused", "That ends after it is due, so it stayed where it was.")]


def test_escape_lets_go_without_moving_anything(qapp: QApplication) -> None:
    rig = Rig(qapp)
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(2, 20 * 60), release=False)
    QTest.keyClick(rig.canvas, Qt.Key.Key_Escape)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, rig.at(2, 20 * 60), False)
    assert rig.said == [] and rig.hand.preview is None and not rig.hand.busy


def test_homework_from_a_tray_is_placed_where_it_is_let_go(qapp: QApplication) -> None:
    rig = Rig(qapp)
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


def test_a_card_laid_at_an_angle_takes_the_time_along_the_card(qapp: QApplication) -> None:
    turned = lambda area: [  # noqa: E731
        LinearTrack(
            day,
            QRectF(area.left() + 40 + day * 95, area.top() + 40, 85, 560),
            Axis.DOWN,
            turn=(day - 3) * 5,
        )
        for day in range(7)
    ]
    rig = Rig(qapp, lay_out=turned, height=660)
    rig.drag(rig.at(2, 18 * 60 + 30), rig.at(3, 20 * 60 + 30))
    assert rig.said == [Move("essay", 2, Span(3, 20 * 60, 21 * 60))]


def test_passing_through_an_edge_does_not_scroll_but_resting_there_does(qapp: QApplication) -> None:
    rig = Rig(qapp, height=1632)
    rig.window.resize(760, 500)
    qapp.processEvents()
    bar = rig.scroll.verticalScrollBar()
    bar.setValue(0)
    bottom = rig.scroll.viewport().mapToGlobal(QPoint(150, rig.scroll.viewport().height() - 10))
    start = rig.at(1, 6 * 60 + 30)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, start, True)
    rig.send(rig.canvas, QEvent.Type.MouseMove, start + QPoint(0, 40), True)
    rig.send(rig.canvas, QEvent.Type.MouseMove, bottom, True)
    QTest.qWait(100)  # through the edge on the way somewhere, briefer than the dwell
    rig.send(rig.canvas, QEvent.Type.MouseMove, bottom - QPoint(0, 80), True)
    QTest.qWait(400)
    assert bar.value() == 0, "passed through the edge: nothing moved"
    rig.send(rig.canvas, QEvent.Type.MouseMove, bottom, True)
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline and bar.value() == 0:
        qapp.processEvents()
    assert bar.value() > 0, "rested at the edge: it scrolls"
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, bottom, False)


def test_double_click_and_enter_open_the_block(qapp: QApplication) -> None:
    rig = Rig(qapp)
    point = rig.at(2, 18 * 60 + 30)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, point, True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    rig.send(rig.canvas, QEvent.Type.MouseButtonDblClick, point, True)
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, point, False)
    QTest.keyClick(rig.canvas, Qt.Key.Key_Return)
    assert rig.said == [("opened", "essay"), ("opened", "essay")]
    assert rig.hand.selection == ("essay", 2)


def test_the_rig_interface_points_at_what_is_drawn(qapp: QApplication) -> None:
    rig = Rig(qapp)
    box = rig.canvas.block_rect("essay", 2)
    assert box is not None and box.contains(rig.at(2, 18 * 60 + 30))
    assert rig.canvas.block_rect("essay", 3) is None


def test_an_edge_held_a_few_pixels_in_does_not_jump_on_the_first_move(qapp: QApplication) -> None:
    """On a 24-hour week that still has room for edges, six pixels is a dozen minutes or so. Pressed
    six pixels inside the end, the end still moves by exactly what the pointer moves, rather than
    first snapping back."""
    rig = Rig(qapp, height=680)
    per_minute = rig.canvas.tracks[0].per_minute()
    assert 10 <= 6 / per_minute <= 14, "six pixels is about twelve minutes at this scale"
    press = rig.at(2, 19 * 60, -6)
    rig.drag(press, press + QPoint(0, round(30 * per_minute)))
    assert rig.said == [Move("essay", 2, Span(2, 18 * 60, 19 * 60 + 30))]
