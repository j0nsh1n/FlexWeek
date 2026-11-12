"""Day dial built from the week every layout test uses, and the readers its tests share. Nothing here
paints or measures: the tests built on it read words, rows, buttons and what a click reaches."""

from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.layouts.base import Scene
from desktop.native.layouts.dial import DayDialView, DialFace
from desktop.native.layouts.registry import options_for, tokens_for
from desktop.native.look import resolved_palette
from desktop.native.reuse import missed_session_ids
from desktop.native.weekmodel import build_week, minute_of
from desktop.native.widgets import FittedLabel
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK

THURSDAY = 3


def shown(
    qapp: QApplication,
    clock: str,
    blocks: list[dict] | None = None,
    today: int | None = THURSDAY,
    homework: dict | None = None,
    **chosen: str,
) -> DayDialView:
    """The dial for Thursday of the test week at `clock`, shown at 1300 by 720. The sessions it calls
    missed are the engine's answer for that clock, as the window asks it."""
    options = {**options_for(None, "dial"), **chosen}
    palette = resolved_palette("light-frost", False, None, "default")
    blocks = BLOCKS if blocks is None else blocks
    homework = homework or HOMEWORK
    week = build_week(WEEK, blocks, homework, TRACE)
    now = datetime(2026, 9, 17, *divmod(minute_of(clock), 60))
    missed = missed_session_ids(blocks, homework, WEEK, now) if today == THURSDAY else frozenset()
    view = DayDialView()
    view.resize(1300, 720)
    view.show_week(
        Scene(
            week,
            today,
            minute_of(clock),
            options,
            tokens_for("dial", options["look"], palette),
            missed=missed,
        )
    )
    view.show()
    qapp.processEvents()
    return view


def text(view: DayDialView, name: str) -> str:
    return view.findChild(QLabel, name).text()


def row_buttons(view: DayDialView) -> list[QPushButton]:
    return [item for item in view.findChildren(QPushButton) if item.property("kind") == "row"]


def rows(view: DayDialView) -> list[tuple[str, str, str, str, str]]:
    """Each row's columns as they read: start, title, length, tag, and whether it is over or on."""
    read = []
    for row in row_buttons(view):
        tag = row.findChild(QLabel, "dialRowTagText")
        read.append(
            (
                row.findChild(QLabel, "dialRowTime").text(),
                row.findChild(FittedLabel, "dialRowName").full_text(),
                row.findChild(QLabel, "dialRowLength").text(),
                tag.text() if tag is not None else "",
                row.property("state"),
            )
        )
    return read


def actions(view: DayDialView) -> list[tuple[str, str]]:
    found = [
        item
        for item in view.findChildren(QPushButton)
        if item.property("kind") != "row" and not item.objectName().startswith("dialRow")
    ]
    return [(item.objectName(), item.property("kind") or "") for item in found]


def face(view: DayDialView) -> DialFace:
    return view.findChild(DialFace, "dialFace")


def reachable(dial: DialFace) -> set[str]:
    """The blocks a click somewhere on the face reaches."""
    hits = set()
    for x in range(0, dial.width(), 5):
        for y in range(0, dial.height(), 5):
            found = dial.block_at(QPointF(x, y))
            if found is not None:
                hits.add(found.block_id)
    return hits


def on_ring(dial: DialFace, minute: float, reach: float | None = None) -> QPointF:
    """A point of the face at `minute`, halfway across the ring or at `reach` from the centre."""
    track = dial.track
    middle = track.point_for(round(minute))
    if reach is None:
        return QPointF(middle)
    scale = reach / math.hypot(middle.x() - track.centre.x(), middle.y() - track.centre.y())
    return track.centre + (QPointF(middle) - track.centre) * scale


def arc_words(view: DayDialView) -> list[str]:
    """The words the face plans to write along its arcs."""
    return [arc.words for arc in face(view).arc_labels()]
