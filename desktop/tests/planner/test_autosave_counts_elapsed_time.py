"""Autosave waits for the student to stop changing things, counted in elapsed time, not by the time of
day: a computer whose clock is set back still saves the change."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_change_is_saved_after_the_clock_is_set_back(
    qapp: QApplication, window: NativeWindow, clock: FakeClock
) -> None:
    session = window.session
    session.add_block(
        {"id": "piano", "title": "Piano", "kind": "locked", "start": "17:00", "duration_min": 30, "days": [0]}
    )
    assert session.dirty
    clock.move(hours=-1)
    wait_until(qapp, lambda: not session.dirty and not session.busy, timeout=6, what="the change was saved")
    assert [block["id"] for block in session.blocks] == ["piano"]
