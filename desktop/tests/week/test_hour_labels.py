"""The hours are named: the last hour line carries its label in every design, written the way the
clock writes midnight, and the first and the last hour row on screen are named whatever the look and
wherever the week is scrolled to (23:00 was missing at the foot, and a larger look hid the top label)."""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.tests.week.support_painter import Said, a_hand, qapp  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.fonts import load_fonts  # noqa: E402
from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.canvas import BlockPainter  # noqa: E402
from desktop.native.hours.classic import ClassicPainter, ClassicWeek  # noqa: E402
from desktop.native.hours.geometry import Axis, LinearTrack  # noqa: E402
from desktop.native.layouts.bento import BentoPainter  # noqa: E402
from desktop.native.layouts.clay import ClayPainter  # noqa: E402
from desktop.native.layouts.mission import MissionPainter  # noqa: E402
from desktop.native.layouts.registry import MATCH, tokens_for  # noqa: E402
from desktop.native.layouts.retro import RetroPainter, scheme  # noqa: E402
from desktop.native.layouts.timeline import TimelinePainter  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week, set_clock_24h  # noqa: E402


def painters() -> dict[str, BlockPainter]:
    palette = resolved_palette("light-frost", False, None)

    def tokens(design: str) -> dict[str, str]:
        return tokens_for(design, MATCH, palette)

    return {
        "plain": BlockPainter(tokens("clay")),
        "today": ClassicPainter(tokens("clay")),
        "bento": BentoPainter(tokens("bento")),
        "retro": RetroPainter(scheme(tokens("retro"))),
        "clay": ClayPainter(tokens("clay"), full=True),
        "timeline": TimelinePainter(tokens("timeline")),
        "mission": MissionPainter(tokens("mission")),
    }


def labels_of(painting: BlockPainter) -> list[str]:
    """The hour labels a design writes beside one day's hours, 06:00 to the end of the day."""
    words: list[str] = []
    across = isinstance(painting, MissionPainter)
    area = QRectF(160, 60, 800, 36) if across else QRectF(80, 10, 120, 1100)
    axis, first = (Axis.ACROSS, 0) if across else (Axis.DOWN, 6 * 60)
    track = LinearTrack(0, area, axis, first=first, last=24 * 60)

    class Wrote(QPainter):
        def drawText(self, *args) -> None:  # noqa: N802
            words.append(next(arg for arg in reversed(args) if isinstance(arg, str)))
            super().drawText(*args)

    picture = QImage(1200, 1200, QImage.Format.Format_ARGB32)
    paint = Wrote(picture)
    paint.setFont(QFont("Inter", 11))
    try:
        painting.hour_labels(paint, track, 56)
    finally:
        paint.end()
    return words


@pytest.mark.parametrize("twenty_four, midnight", [(True, "24:00"), (False, "12:00 AM")])
@pytest.mark.parametrize("design", ["plain", "today", "bento", "retro", "clay", "timeline", "mission"])
def test_the_last_hour_line_is_labelled_in_every_design_as_the_clock_writes_midnight(
    design: str, twenty_four: bool, midnight: str
) -> None:
    load_fonts()
    set_clock_24h(twenty_four)
    try:
        written = labels_of(painters()[design])
    finally:
        set_clock_24h(True)
    assert midnight in written, (design, written)


LOOKS = [
    ("system", None),
    ("light-frost", None),
    ("light-frost", {"text": "large"}),
    ("dark-frost", {"text": "large"}),
    ("slate", {"text": "small"}),
    ("system", {"preset": "high-contrast"}),
]


def shown(pack: str, look: dict | None) -> ClassicWeek:
    """A week with no time now on it, so no label gives way to the pill that says the time."""
    app = QApplication.instance()
    view = ClassicWeek(a_hand())
    view.set_look(look, resolved_palette(pack, False, look))
    view.set_week(build_week("2026-09-21", [], {}, None), None, None)
    view.resize(980, 500)
    view.show()
    app.processEvents()
    view.hours.relayout()
    app.processEvents()
    return view


def hour_words(view: ClassicWeek) -> list[str]:
    Said.words = []
    view.hours.repaint()
    return [text for text, _where in Said.words if text.endswith(":00") and len(text) == 5]


@pytest.mark.parametrize(("pack", "look"), LOOKS)
def test_the_first_and_last_hour_on_screen_are_named_at_every_scroll_position(
    monkeypatch: pytest.MonkeyPatch, pack: str, look: dict | None
) -> None:
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    view = shown(pack, look)
    bar = view.scroll.verticalScrollBar()
    track = view.hours.track_for(3)
    assert track is not None and bar.maximum() > 0
    for value in sorted({*range(0, bar.maximum(), 7), bar.maximum()}):
        bar.setValue(value)
        QApplication.instance().processEvents()
        visible = view.hours._visible()
        rows = [
            hour
            for hour in range(24)
            if visible.top() <= track.area.top() + track.offset(hour * 60) <= visible.bottom()
        ]
        said = hour_words(view)
        for hour in (rows[0], rows[-1]):
            assert f"{hour:02d}:00" in said, f"scrolled to {value}: {hour:02d}:00 is on screen, unnamed"
