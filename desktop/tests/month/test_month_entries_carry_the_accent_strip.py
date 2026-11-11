# ruff: noqa: F811
"""Every Material month entry has the coloured left strip its block or homework has in Week and Day, in
the same colour: a fixed block's chip, a homework session's chip and a homework due chip.

The expected colour is read from the same item's Week block, never written down here. Clock Thursday 19:00,
School on weekday mornings, History essay with a session on that Thursday and due on Sunday
(support_material_month.seed_school_and_essay).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import named, pump  # noqa: E402
from desktop.tests.month.support_material_month import (  # noqa: E402
    bridge,
    cell,
    named_on,
    open_month,
    seed_school_and_essay,
    texts,
)


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-strip"])


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    made = open_light((1280, 800))
    seed_school_and_essay(made)
    return made


def colour_of(bar: QObject) -> str:
    return QColor(bar.property("color")).name()


def week_strip(root: QObject, title: str) -> str:
    for block in named(root, "weekBlock"):
        if any(str(label.property("text")) == title for label in named(block, "title")):
            bars = [bar for bar in named(block, "bar") if bar.property("visible") is True]
            assert bars, f"{title} has no strip in Week"
            return colour_of(bars[0])
    raise AssertionError(f"no Week block named {title}")


def month_strip(root: QObject, iso: str, words: str) -> QObject | None:
    """The strip of the chip in that date whose words contain `words`, or None when it has none."""
    for chip in named_on(cell(root, iso), "monthChip"):
        if any(words in text for text in texts(chip, "monthChipText")):
            bars = named_on(chip, "monthChipBar")
            return bars[0] if bars else None
    raise AssertionError(f"no chip with {words!r} on {iso}")


def test_month_entries_have_the_strip_of_the_same_item_in_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, _month = open_month(qapp, window)
    monday = date.fromisoformat(window.session.week_start)
    thursday = (monday + timedelta(days=3)).isoformat()
    sunday = (monday + timedelta(days=6)).isoformat()
    school_in_month = month_strip(root, thursday, "School")
    session_in_month = month_strip(root, thursday, "History essay")
    due_in_month = month_strip(root, sunday, "History essay")
    for strip in (school_in_month, session_in_month, due_in_month):
        assert strip is not None, "a month entry has no strip"
    month_colours = (colour_of(school_in_month), colour_of(session_in_month), colour_of(due_in_month))

    bridge(window).showPage("week")
    pump(qapp, 40)
    assert month_colours[0] == week_strip(root, "School")
    assert month_colours[1] == week_strip(root, "History essay")
    assert month_colours[2] == week_strip(root, "History essay")
    assert month_colours[0] != month_colours[1], "a class and homework must not share one colour"
