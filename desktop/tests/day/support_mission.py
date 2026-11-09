"""What Mission control's tests share: its view made on the test week, and the readers of its figures,
its deadline table and the minutes its lanes show.

The view is made from a Scene on the test week (Thursday 17 September, 13:40 unless told otherwise), so
a test names the minute it is at and never reads the clock.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextDocumentFragment
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from desktop.native.hours.chips import TrayChip
from desktop.native.hours.hand import Hand
from desktop.native.hours.zoom import HoursScroll
from desktop.native.layouts.base import Scene
from desktop.native.layouts.mission import MissionCanvas, MissionView
from desktop.native.layouts.registry import LEGACY_COLOURS, options_for, tokens_for
from desktop.native.look import design_look
from desktop.native.weekmodel import build_week, minute_of
from desktop.native.widgets import FittedLabel
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK, block

__all__ = [
    "BLOCKS",
    "HOMEWORK",
    "block",
    "figure",
    "last_minute_shown",
    "minutes_shown",
    "shown",
    "table_rows",
    "words",
]

# Two surfaces whose lanes open by the same rule: the scroll area each keeps its lanes in.
SURFACES = [("week", "missionWeekScroll", {}), ("day", "missionDayScroll", {"iso_day": "2026-09-17"})]


def shown(
    qapp: QApplication,
    *,
    surface: str = "week",
    blocks: list[dict] | None = None,
    homework: dict | None = None,
    iso_day: str = "",
    today: int | None = 3,
    minute: str = "13:40",
    size: tuple[int, int] = (1366, 760),
    scale: float = 1.0,
    hand: Hand | None = None,
    focus: str = "",
    **chosen: str,
) -> MissionView:
    """Mission on the test week, Thursday 13:40 unless told otherwise."""
    if "colour" in chosen:
        chosen["look"] = LEGACY_COLOURS["mission"].get(chosen.pop("colour"), "your")
    options = {**options_for(None, "mission"), **chosen}
    palette, _look = design_look(options["look"], "light-frost", False, None)
    view = MissionView(hand=hand)
    view.resize(*size)
    week = build_week(WEEK, blocks or BLOCKS, homework or HOMEWORK, TRACE)
    view.show_week(
        Scene(
            week,
            today,
            minute_of(minute),
            options,
            tokens_for("mission", options["look"], palette),
            scale=scale,
            surface=surface,
            iso_day=iso_day,
            focus=focus,
        )
    )
    view.show()
    qapp.processEvents()
    return view


def words(widget: QLabel) -> str:
    """What a label says, its markup and spacing aside."""
    return " ".join(QTextDocumentFragment.fromHtml(widget.text()).toPlainText().split())


def figure(view: MissionView, name: str) -> tuple[str, str]:
    """A figure's value and the line under it."""
    return words(view.findChild(QLabel, f"{name}Value")), words(view.findChild(QLabel, f"{name}Line"))


def table_rows(view: MissionView) -> list[tuple[str, str, str, str]]:
    """Each row of the deadline table: the homework, what it needs, the time left and where it is."""
    rows = []
    for row in view.findChild(QFrame, "missionDeadlines").findChildren(QFrame, "missionDeadline"):
        placed = row.findChild(QLabel, "missionPlaced")
        chips = " / ".join(chip.text() for chip in row.findChildren(TrayChip))
        where = words(placed) if placed is not None else chips
        rows.append(
            (
                row.findChild(FittedLabel, "missionDeadlineTitle").full_text(),
                row.findChild(QLabel, "missionFigure").text(),
                row.findChild(QLabel, "missionLeft").text(),
                where,
            )
        )
    return rows


def minutes_shown(view: MissionView, name: str) -> tuple[float, float]:
    """The minutes at the left and right edges of the lanes as they are scrolled."""
    scroll = view.findChild(HoursScroll, name)
    track = view.findChild(MissionCanvas, "missionHours").tracks[0]
    along = scroll.horizontalScrollBar().value()
    return tuple(
        track.first + (edge - track.area.left()) / track.per_minute()
        for edge in (along, along + scroll.viewport().width())
    )


def last_minute_shown(view: MissionView, name: str) -> float:
    return minutes_shown(view, name)[1]
