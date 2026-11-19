"""One word for one thing, everywhere: a finished block says "Finished", the tray is "Not placed yet", and
the strip under Next says what it is (0.15 rows 13, 16 and 17)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from backend.tests.fake_clock import CLOCK
from desktop.native.hours.canvas import Drawn
from desktop.native.hours.geometry import Span
from desktop.native.weekmodel import LEFTOVER
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _add_essay(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "estimate_min": 60,
            "revision": 0,
            "due": session.week_start[:10] + "T23:59",
        }
    )
    session.save()
    settled(qapp, window)


def test_a_finished_block_says_finished() -> None:
    block = Drawn("essay", "History essay", "", True, Span(3, 19 * 60, 20 * 60), 0, 1, done=True)
    assert block.detail == "19:00–20:00 · 1 h · Finished"


def test_the_tray_is_not_placed_yet(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    assert LEFTOVER["needs_time"] == "Not placed yet"
    _add_essay(qapp, window)
    window._on_week()
    qapp.processEvents()
    assert window.findChild(QLabel, "classicWaitingLabel").text() == "No time yet · drag onto a day"


def test_the_strip_under_next_says_what_it_is(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    _add_essay(qapp, window)
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.add_block({**essay, "start": "19:00", "days": [0], "pinned": True})
    session.save()
    settled(qapp, window)
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(hours=18))
    session.week_changed.emit()
    settled(qapp, window)
    panel = window.rail
    assert not panel.tasks.isVisibleTo(window)
    assert not panel.focus.isVisible()
    assert panel.next.start_focus.isVisible()
    assert panel.next.start_focus.text() == "Start focus"
    assert panel.next.title.text() == "History essay"
