# ruff: noqa: F811
"""The week saves itself: after the student stops changing things, never on a conflict, never on top of a
request in flight."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    wait_until,
    window,  # noqa: F401
)


def test_the_week_saves_itself_without_anyone_pressing_save(qapp: QApplication, window: NativeWindow) -> None:
    """Save left the bar, so this is the only thing that writes a student's week. If it stops working,
    work is lost silently, which is the worst failure this app has."""
    before = window.session.revision
    window.session.add_homework(
        {
            "id": "auto",
            "title": "Autosaved essay",
            "due": sunday_due(window.session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    assert window.session.dirty is True
    # Move the debounce's start back rather than waiting for it.
    window._changed_ms = 0
    window._last_try_ms = 0
    window._autosave_tick()
    wait_until(qapp, lambda: not window.session.busy and window.session.revision > before)
    assert window.session.dirty is False


def test_autosave_waits_until_the_student_stops_changing_things(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Dragging a block emits a change per step. Saving on each one would post continuously."""
    window.session.dirty = True
    window.session.pending_save = None
    # The autosave measures time since the last change on the monotonic clock, as a duration.
    window._changed_ms = int(time.monotonic() * 1000)
    posted = []
    window.session.save = lambda *a, **k: posted.append(1)
    window._autosave_tick()
    assert posted == [], "saved while the student was still changing things"


def test_autosave_keeps_its_hands_off_a_conflict(qapp: QApplication, window: NativeWindow) -> None:
    """A 409 means another window wrote this week. Answering that is the student's decision, and a timer
    that retried would overwrite whichever copy lost the race."""
    window.session.dirty = True
    window.session.conflict = True
    window._changed_ms = 0
    posted = []
    window.session.save = lambda *a, **k: posted.append(1)
    window._autosave_tick()
    assert posted == []


def test_autosave_does_not_pile_requests_on_a_busy_session(qapp: QApplication, window: NativeWindow) -> None:
    window.session.dirty = True
    window.session.conflict = False
    window.session.busy = True
    window._changed_ms = 0
    posted = []
    window.session.save = lambda *a, **k: posted.append(1)
    window._autosave_tick()
    window.session.busy = False
    assert posted == []
