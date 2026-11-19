"""What the motion tests share: bare pages to switch between, a week of hours on screen, and steps of
the animation time (desktop/tests/motion_support.py) in place of waiting."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget, QWidget

from desktop.native import motion
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





LATER = [occurrence("essay", 3, 15 * 60, 16 * 60), occurrence("club", 5, 12 * 60, 13 * 60)]
