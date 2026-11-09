"""Shared set-up for the Timeline planner's tests: the view shown on its own in a host of a fixed size,
lookups into it, the fold's handle and the painter that keeps the words the hours draw. Not a test
module."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QPainter, QTextDocument  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget  # noqa: E402

from desktop.native.fonts import load_fonts  # noqa: E402
from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.native.hours.zoom import HoursScroll  # noqa: E402
from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.registry import LEGACY_COLOURS, options_for, tokens_for  # noqa: E402
from desktop.native.layouts.timeline import TimelineCanvas, TimelineView  # noqa: E402
from desktop.native.look import design_look, resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402

THURSDAY = 3
HOSTS: list = []


def scene_of(
    tab: str = "week",
    clock: str = "13:40",
    blocks: list[dict] | None = None,
    homework: dict | None = None,
    palette: dict | None = None,
    today: int = THURSDAY,
    **chosen: str,
) -> Scene:
    if "colour" in chosen:
        chosen["look"] = LEGACY_COLOURS["timeline"].get(chosen.pop("colour"), "your")
    options = {**options_for(None, "timeline"), **chosen}
    palette = palette or resolved_palette("light-frost", False, None, "default")
    if options["look"] != "your":
        palette, _look = design_look(
            options["look"], "system", palette.get("axis") == "dark", None, palette["accent"]
        )
    week = build_week(
        WEEK, BLOCKS if blocks is None else blocks, HOMEWORK if homework is None else homework, TRACE
    )
    return Scene(
        week,
        today,
        minute_of(clock),
        options,
        tokens_for("timeline", options["look"], palette),
        surface=tab,
        iso_day=week.date_of(today).isoformat(),
    )


def shown(
    qapp: QApplication, tab: str = "week", size: tuple[int, int] = (1280, 744), **given
) -> TimelineView:
    load_fonts()
    host = QWidget()
    HOSTS.append(host)
    # The window's stylesheet gives every widget the body face at Normal text, and what fits in a
    # block depends on it.
    host.setStyleSheet("QWidget { font-family: Inter; font-size: 13pt; }")
    QVBoxLayout(host).setContentsMargins(0, 0, 0, 0)
    view = TimelineView()
    host.layout().addWidget(view)
    host.resize(*size)
    view.show_week(scene_of(tab, **given))
    host.show()
    for _ in range(3):
        qapp.processEvents()
    return view


def canvas(view: TimelineView) -> TimelineCanvas:
    found = view.hours_surfaces()
    assert len(found) == 1 and isinstance(found[0], TimelineCanvas)
    return found[0]


def scroll_of(view: TimelineView) -> HoursScroll:
    area = canvas(view)._scroll_area()
    assert isinstance(area, HoursScroll)
    return area


def page_of(view: TimelineView) -> QScrollArea:
    return view.findChild(QScrollArea, "timelineScroll")


def texts(view: TimelineView, name: str) -> list[str]:
    return [item.text() for item in view.findChildren(QLabel, name) if item.isVisible()]


def plain(item: QLabel) -> str:
    """A label's words as read, without the markup that colours some of them."""
    document = QTextDocument()
    document.setHtml(item.text())
    return document.toPlainText()


class Said(QPainter):
    """Every text the hours draw, as they draw it."""

    words: list[str] = []

    def drawText(self, *args) -> None:  # noqa: N802
        Said.words.append(next(arg for arg in reversed(args) if isinstance(arg, str)))
        super().drawText(*args)


def drawn_words(monkeypatch: pytest.MonkeyPatch, view: TimelineView) -> list[str]:
    monkeypatch.setattr(canvas_module, "QPainter", Said)
    Said.words = []
    canvas(view).repaint()
    return list(Said.words)


# The fold between the pages: a handle in the row of day names, dragged or stepped


def handle_of(view: TimelineView) -> QWidget:
    found = view.findChild(QWidget, "timelineFold")
    assert found is not None and found.isVisible(), "the fold has its handle"
    return found


def pages(view: TimelineView) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The days on each page, read from where the gutter falls between the columns."""
    tracks = canvas(view).tracks
    gaps = [at for at in range(1, 7) if tracks[at].area.left() - tracks[at - 1].area.right() > 20]
    assert len(gaps) == 1, f"one gutter, not {gaps}"
    return tuple(range(gaps[0])), tuple(range(gaps[0], 7))


def centre_of(widget: QWidget) -> QPointF:
    return widget.mapToGlobal(QRectF(widget.rect()).center())


def over(view: TimelineView, day: int, share: float) -> QPointF:
    """A point in the row of day names over `day`, `share` of the way across its column."""
    hours = canvas(view)
    area = hours.tracks[day].area
    across = hours.mapToGlobal(QPointF(area.left() + area.width() * share, 0)).x()
    return QPointF(across, centre_of(handle_of(view)).y())


def press(widget: QWidget, kind: QEvent.Type, at: QPointF, held: bool) -> None:
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    QApplication.sendEvent(
        widget,
        QMouseEvent(
            kind,
            widget.mapFromGlobal(at),
            at,
            Qt.MouseButton.LeftButton,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def drag_fold(qapp: QApplication, view: TimelineView, to: QPointF, held=None) -> object:
    """Press the handle, carry it to `to` in steps, run `held` while it is still pressed, let go."""
    handle = handle_of(view)
    start = centre_of(handle)
    press(handle, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 7):
        press(handle, QEvent.Type.MouseMove, start + (to - start) * (step / 6), True)
    qapp.processEvents()
    seen = held() if held is not None else None
    press(handle, QEvent.Type.MouseButtonRelease, to, False)
    qapp.processEvents()
    return seen


def kept_by(view: TimelineView) -> list[tuple[str, str]]:
    kept: list[tuple[str, str]] = []
    view.option_set.connect(lambda key, value: kept.append((key, value)))
    return kept


def tap(qapp: QApplication, view: TimelineView, where: str) -> str:
    """Click the fold's handle at its back arrow, its forward arrow or its middle; what it says after."""
    handle = handle_of(view)
    across = {"back": 3, "forward": handle.width() - 4, "middle": handle.width() // 2}[where]
    QTest.mouseClick(handle, Qt.MouseButton.LeftButton, pos=QPoint(across, handle.height() // 2))
    qapp.processEvents()
    return handle_of(view).text()
