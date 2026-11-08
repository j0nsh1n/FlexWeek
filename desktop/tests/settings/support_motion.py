"""What the motion tests share: bare pages to switch between, a week of hours on screen, and steps of
the animation time (desktop/tests/motion_support.py) in place of waiting."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF
from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget, QVBoxLayout, QWidget

from desktop.native import motion
from desktop.native.hours.canvas import BlockPainter, HoursCanvas
from desktop.native.hours.geometry import LinearTrack
from desktop.native.hours.hand import Hand, Verdict
from desktop.native.look import resolved_palette
from desktop.native.motion import (
    FADE_NAME,
    PAGE_IN_AFTER_MS,
    PAGE_IN_MS,
    PAGE_OUT_MS,
    SLIDE_NAME,
    duration,
)
from desktop.native.weekmodel import Occurrence
from desktop.tests.motion_support import ManualTime

# Long enough for a page to fade through at the slowest level.
THROUGH_MS = duration(max(PAGE_OUT_MS, PAGE_IN_AFTER_MS + PAGE_IN_MS), "extra") + 150


def pictures(host: QWidget) -> list[QLabel]:
    return [label for label in host.findChildren(QLabel, FADE_NAME) if label.isVisible()]


def slides(host: QWidget) -> list[QLabel]:
    return [label for label in host.findChildren(QLabel, SLIDE_NAME) if label.isVisible()]


def two_pages(qapp: QApplication) -> tuple[QStackedWidget, QWidget, QWidget]:
    stack = QStackedWidget()
    first, second = QLabel("Week"), QLabel("Month")
    stack.addWidget(first)
    stack.addWidget(second)
    stack.resize(400, 300)
    stack.show()
    qapp.processEvents()
    return stack, first, second


def forget_dead_clocks() -> None:
    """A window an earlier test closed can leave a clock in motion's running set whose timer is gone;
    ManualTime.advance asks every running clock about its timer."""
    for clock in list(motion._RUNNING):
        try:
            clock._timer.isActive()
        except RuntimeError:
            motion._RUNNING.discard(clock)


def move_on(manual_time: ManualTime, ms: int) -> None:
    """Move the animation time `ms` on, then let the pictures a finished fade deleted go."""
    forget_dead_clocks()
    manual_time.advance(ms)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def occurrence(block_id: str, day: int, start: int, end: int) -> Occurrence:
    title = block_id.title()
    return Occurrence(block_id, title, "class", day, start, end, False, False, False, None, None, None)


class Hours:
    """A week of hours on screen, with the hand that the window would own."""

    def __init__(self, qapp: QApplication) -> None:
        self.window = QWidget()
        self.window.resize(420, 500)
        self.hand = Hand(lambda block_id, from_day, span: Verdict(True, ""), self.window)
        self.canvas = HoursCanvas(
            self.hand,
            BlockPainter(resolved_palette("system", False, None)),
            lambda area: [
                LinearTrack(day, QRectF(area.left() + day * 60, area.top(), 60, area.height()), first=480)
                for day in range(7)
            ],
        )
        QVBoxLayout(self.window).addWidget(self.canvas)
        self.canvas.set_week([occurrence("essay", 1, 9 * 60, 10 * 60)])
        self.window.show()
        qapp.processEvents()

    def picture(self):  # noqa: ANN201
        return self.canvas.grab().toImage()

    def settled_picture(self, week: list[Occurrence]):  # noqa: ANN201
        """The week as it looks with nothing moving: drawn on a fresh canvas of the same size."""
        other = Hours.__new__(Hours)
        other.window = QWidget()
        other.window.resize(self.window.size())
        other.hand = Hand(lambda block_id, from_day, span: Verdict(True, ""), other.window)
        other.canvas = HoursCanvas(other.hand, self.canvas.painter, self.canvas._lay_out)
        QVBoxLayout(other.window).addWidget(other.canvas)
        other.window.show()
        QApplication.processEvents()
        other.canvas.set_week(week)
        picture = other.picture()
        other.window.close()
        return picture


LATER = [occurrence("essay", 3, 15 * 60, 16 * 60), occurrence("club", 5, 12 * 60, 13 * 60)]
