"""What the Bento design's tests share: a Bento view made on the test week, and the small readers of it.

The view is made from a Scene on the test week (Thursday 17 September, 13:40 unless told otherwise), so
a test names the minute it is at and never reads the clock.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.hours.canvas import HoursCanvas
from desktop.native.layouts.base import Scene
from desktop.native.layouts.bento import BentoView
from desktop.native.layouts.registry import LEGACY_COLOURS, options_for, tokens_for
from desktop.native.look import design_look
from desktop.native.weekmodel import build_week, minute_of
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK


def scene(
    surface: str = "week",
    *,
    clock: str = "13:40",
    blocks: list[dict] | None = None,
    homework: dict | None = None,
    iso_day: str = "2026-09-17",
    today: int | None = 3,
    scale: float = 1.0,
    **chosen: str,
) -> Scene:
    if "colour" in chosen:
        chosen["look"] = LEGACY_COLOURS["bento"].get(chosen.pop("colour"), "your")
    options = {**options_for(None, "bento"), **chosen}
    palette, _look = design_look(options["look"], "light-frost", False, None)
    week = build_week(
        WEEK,
        BLOCKS if blocks is None else blocks,
        HOMEWORK if homework is None else homework,
        TRACE,
    )
    return Scene(
        week,
        today,
        minute_of(clock),
        options,
        tokens_for("bento", options["look"], palette),
        scale=scale,
        surface=surface,
        month={"month": "2026-09", "days": []} if surface == "month" else None,
        iso_day=iso_day,
    )


def shown(
    qapp: QApplication,
    surface: str = "week",
    *,
    size: tuple[int, int] = (1150, 768),
    **given: object,
) -> BentoView:
    view = BentoView()
    view.resize(*size)
    view.show_week(scene(surface, **given))
    view.show()
    qapp.processEvents()
    return view


def text(view: BentoView, name: str) -> str:
    found = view.findChild(QLabel, name)
    assert found is not None, name
    return found.text()


def texts(view: BentoView, name: str) -> list[str]:
    return [item.text() for item in view.findChildren(QLabel, name) if item.isVisible()]


def hours(view: BentoView, name: str = "bentoDayHours") -> HoursCanvas:
    found = view.findChild(HoursCanvas, name)
    assert found is not None and found.isVisible(), name
    return found


class Wrote(QPainter):
    """A painter that keeps every word it writes and the box it writes it in. Put in place of a
    module's QPainter, it is the one a real paint event draws with."""

    words: list[tuple[str, QRectF]] = []

    def drawText(self, *args: object) -> None:  # noqa: N802
        words = next(arg for arg in reversed(args) if isinstance(arg, str))
        where = next((arg for arg in args if isinstance(arg, QRectF)), QRectF())
        Wrote.words.append((words, QRectF(where)))
        super().drawText(*args)
