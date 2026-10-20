"""The Agenda rail is 260 px wide and nothing in it runs past that: a long homework title ends in
"…" so Start focus and the day it is due stay whole (Fable's 1.0.0 audit, must-fix 2)."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="needs PySide6")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QLabel, QPushButton

    from desktop.tests.test_hours_open import qapp, wait_until, window  # noqa: F401

LONG = "A very long assignment title that must fit the narrow Agenda rail"


def _right(widget, rail) -> int:
    return widget.mapTo(rail, widget.rect().topRight()).x()


def test_a_long_title_never_pushes_the_rails_rows_past_its_edge(qapp, window) -> None:  # noqa: F811
    session = window.session
    session.add_homework(
        {"id": "rail-work", "title": LONG, "due": "2026-10-16T23:59", "estimate_min": 60, "revision": 0}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = next(item["id"] for item in session.blocks if item.get("assignment_id") == "rail-work")
    session.hand_move(block, -1, 3, 16 * 60, 17 * 60)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    for _ in range(5):
        qapp.processEvents()
    rail = window.rail
    assert rail.width() == 260
    assert rail.body.width() <= rail.scroll.viewport().width()
    focus = rail.findChild(QPushButton, "railNextFocus")
    assert focus.isVisible() and _right(focus, rail) <= rail.width()
    # The rows in the list now; a row replaced by this refresh waits for the event loop to delete it.
    listed = [rail.due_list.itemAt(index).widget() for index in range(rail.due_list.count())]
    rows = [row.findChild(QLabel, "railDueTitle") for row in listed if row is not None]
    assert rows, "the long homework is due this week"
    for title in rows:
        when = title.parentWidget().findChild(QLabel, "railDueWhen")
        assert _right(when, rail) <= rail.width(), f"{when.text()!r} runs past the rail"
        assert when.text() == "Fri"
    long_row = next(title for title in rows if title.full_text() == LONG)
    assert long_row.text().endswith("…")
    assert long_row.accessibleName() == LONG
    # A Next row's name wraps whole beside its Start focus, inside the rail.
    for row in rail.next.rest.findChildren(QLabel, "railNextRowTitle"):
        if row.isVisible():
            assert "…" not in row.text() and _right(row, rail) <= rail.width()
    for start in rail.next.rest.findChildren(QPushButton, "railNextRowFocus"):
        if start.isVisible():
            assert _right(start, rail) <= rail.width()
            assert start.width() >= start.sizeHint().width(), "Start focus is cut"
