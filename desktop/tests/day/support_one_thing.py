"""One thing, the day screen, built from the week every layout test uses, and the readers its tests
share. Nothing here paints or measures."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.layouts.base import Scene
from desktop.native.layouts.one_thing import OneThingView
from desktop.native.layouts.registry import LEGACY_COLOURS, options_for, tokens_for
from desktop.native.look import design_look
from desktop.native.ring import CountdownRing
from desktop.native.weekmodel import build_week, minute_of
from desktop.native.widgets import FittedLabel
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK

THURSDAY = 3


def scene(clock: str, today: int | None = THURSDAY, accent: str = "default", **chosen: str) -> Scene:
    if "colour" in chosen:
        chosen["look"] = LEGACY_COLOURS["one"].get(chosen.pop("colour"), "your")
    options = {**options_for(None, "one"), **chosen}
    palette, _look = design_look(options["look"], "light-frost", False, None, accent)
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    return Scene(week, today, minute_of(clock), options, tokens_for("one", options["look"], palette))


def shown(
    qapp: QApplication,
    clock: str,
    today: int | None = THURSDAY,
    size: tuple[int, int] = (1200, 820),
    **chosen: str,
) -> OneThingView:
    view = OneThingView()
    view.resize(*size)
    view.show_week(scene(clock, today, **chosen))
    view.show()
    qapp.processEvents()
    return view


def says(view: OneThingView) -> tuple[str, str, str]:
    # The title breaks onto a second line when the demo's smaller ring needs it; the words are what count.
    label, title, line = (view.findChild(QLabel, name).text() for name in ("oneLabel", "oneTitle", "oneLine"))
    return label, " ".join(title.split()), line


def ring_of(view: OneThingView) -> CountdownRing:
    return view.findChild(CountdownRing)


def counts(view: OneThingView) -> tuple[str, float]:
    """The ring's number and the share of its hour still to go."""
    ring = ring_of(view)
    return ring.number(), round(ring.left(), 3)


def then(view: OneThingView) -> list[str]:
    """What the Then list shows, a row each, as the student reads it across."""
    rows = [row for row in view.findChildren(QLabel, "oneRowTime") if row.isVisibleTo(view)]
    return [
        " ".join(
            [
                row.text(),
                row.parent().findChild(FittedLabel, "oneRowName").full_text(),
                row.parent().findChild(QLabel, "oneRowLength").text(),
            ]
        )
        for row in rows
    ]


def buttons(view: OneThingView) -> list[str]:
    # The day letters under the bar are buttons too; they are checked by their own tests.
    return [
        button.objectName()
        for button in view.findChildren(QPushButton)
        if not button.objectName().startswith("oneDay")
    ]


def press(view: OneThingView, key: Qt.Key) -> None:
    view.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def full_title(view: OneThingView) -> str:
    """The ring shortens a long title with an ellipsis; the whole words are its accessible name."""
    return view.findChild(QLabel, "oneTitle").accessibleName()
