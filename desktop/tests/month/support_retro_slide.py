"""What the Retro Month slide tests share: recording every frame of a motion, and the steps that put the
window in a design and press a view button. (test_motion_0185.py reaches `in_design`, `nothing_left_over`,
`press`, `settle_everything` and `watch` through the old module path test_retro_month_slide.py.)"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QWidget

import desktop.native.motion as motion
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.motion import FADE_NAME, SLIDE_NAME, Dim, apply_ui_effects
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

if TYPE_CHECKING:
    import pytest


@dataclass
class Frame:
    at: float
    total: int
    slides: list[int]
    fades: int
    dims: list[float]
    offsets: list[int]


@dataclass
class Seen:
    frames: list[Frame] = field(default_factory=list)

    def with_dim(self) -> list[Frame]:
        return [frame for frame in self.frames if frame.dims]

    def slid(self, length: int) -> list[Frame]:
        """The frames of the one motion that dims, which the pieces fading beside it (other lengths)
        are not."""
        return [frame for frame in self.with_dim() if frame.total == length]

    def with_fade(self) -> list[Frame]:
        return [frame for frame in self.frames if frame.fades]

    def with_slide(self) -> list[Frame]:
        return [frame for frame in self.frames if frame.slides]


def pictures_over(page: QWidget) -> tuple[list[QLabel], list[QLabel], list[Dim]]:
    """The slide, the held pictures and the dims on `page`. Walks `children()`, not `findChildren()`."""
    labels = [kid for kid in page.children() if isinstance(kid, QLabel) and kid.isVisible()]
    slides = [label for label in labels if label.objectName() == SLIDE_NAME]
    # The picture of the desk or month, trimmed to what changed, not a small one of a part of it.
    tall = page.height() // 2
    fades = [label for label in labels if label.objectName() == FADE_NAME and label.height() > tall]
    dims = [kid for holder in (page, *fades) for kid in holder.children() if isinstance(kid, Dim)]
    return slides, fades, dims


def watch(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> Seen:
    """Record what is over the week page after every frame of every motion that runs."""
    seen = Seen()
    page = window._week_page
    real_run = motion._run

    def spy(owner, total, step, done):  # type: ignore[no-untyped-def]
        def recorded(at: float) -> None:
            step(at)
            slides, fades, dims = pictures_over(page)
            offsets = [
                effect.offset.x()
                for effect in (label.graphicsEffect() for label in fades)
                if effect is not None and hasattr(effect, "offset")
            ]
            shares = [dim.share for dim in dims]
            seen.frames.append(Frame(at, total, [label.x() for label in slides], len(fades), shares, offsets))

        real_run(owner, total, recorded, done)

    monkeypatch.setattr(motion, "_run", spy)
    return seen


def settle_everything(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not motion.busy())
    still(window)
    qapp.processEvents()


def in_design(qapp: QApplication, window: NativeWindow, design: str, level: str = "normal") -> None:
    window.session.preferences = {**(window.session.preferences or {}), "motion": level}
    window._motion = level
    apply_ui_effects(level)
    window._layout = sanitize_layout({"main": design, "day": "one"})
    window._apply_appearance()
    window.resize(1280, 800)
    window.show()
    window.session.set_view("week")
    window._on_week()
    settle_everything(qapp, window)


def press(qapp: QApplication, window: NativeWindow, name: str, until: Callable[[], bool]) -> None:
    window.findChild(QAbstractButton, name).click()
    wait_until(qapp, until)
    settle_everything(qapp, window)


def month_board(window: NativeWindow) -> QWidget | None:
    return window.planner.currentWidget().findChild(QWidget, "layoutMonthBoard")


def month_is_live(window: NativeWindow) -> bool:
    board = month_board(window)
    return window.session.planner_view == "month" and board is not None and board.isVisible()


def nothing_left_over(window: NativeWindow) -> None:
    slides, fades, dims = pictures_over(window._week_page)
    assert slides == [] and fades == [] and dims == [], "no picture or dim stays on screen"
    assert window.planner.updatesEnabled(), "the planner paints again"


def month_from_the_engine(qapp: QApplication, window: NativeWindow) -> dict:
    """A real month snapshot, kept so a test can hand it over at the moment it chooses, then back to
    the week."""
    press(qapp, window, "viewMonth", lambda: month_is_live(window))
    data = window.session.month_data
    assert data is not None
    press(qapp, window, "viewWeek", lambda: window.session.planner_view == "week")
    return data


def month_arrives(window: NativeWindow, data: dict) -> None:
    window.session.month_data = data
    window.session.week_changed.emit()


def slide_in_progress(window: NativeWindow) -> QLabel | None:
    slides, _fades, _dims = pictures_over(window._week_page)
    return slides[0] if slides else None


def live_month_now(window: NativeWindow):  # type: ignore[no-untyped-def]
    """The month on screen once the slide is over, in the area the slide covered."""
    page = window._week_page
    top = window._top_bar.geometry().bottom() + 1
    return page.grab(QRect(0, top, page.width(), page.height() - top)).toImage()


def blank_like(image):  # type: ignore[no-untyped-def]
    """An image of one colour, the page's background, the size of `image`."""
    blank = QImage(image.size(), image.format())
    blank.fill(image.pixelColor(0, image.height() - 1))
    return blank

