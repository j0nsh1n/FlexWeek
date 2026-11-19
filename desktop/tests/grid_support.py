"""A signed-in window with the clock held on a Wednesday, and what the tests that need that share."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.window import NativeWindow
from desktop.tests.light_app import LightWindows
from desktop.tests.light_app import window as signed_in  # noqa: F401
from desktop.tests.window_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_out,
    wait_until,
)

NONE = Qt.KeyboardModifier.NoModifier
WEDNESDAY = 2
PIANO = {
    "id": "piano",
    "kind": "locked",
    "title": "Piano",
    "category": "extra",
    "start": "15:00",
    "duration_min": 60,
    "days": [WEDNESDAY],
}


def hold_clock(window: NativeWindow, day: int, minute: int) -> None:
    CLOCK.set(datetime.fromisoformat(window.session.week_start) + timedelta(days=day, minutes=minute))
    QApplication.processEvents()


@pytest.fixture()
def window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """A signed-in window on Wednesday 14:07 of the open week, with one early block on Monday. Opened
    here, so a test file needs only this fixture and qapp."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        yield from _week_with_an_early_block(qapp, windows.open())
    finally:
        windows.close()


def _week_with_an_early_block(qapp: QApplication, signed_in: NativeWindow) -> Iterator[NativeWindow]:
    signed_in.resize(1280, 860)
    signed_in.session.add_block({**PIANO, "id": "early", "title": "Early", "start": "06:00", "days": [0]})
    signed_in.session.save()
    settled(qapp, signed_in)
    signed_in.session.set_view("week")
    settled(qapp, signed_in)
    signed_in.show()
    assert QTest.qWaitForWindowExposed(signed_in)
    signed_in.activateWindow()
    wait_until(qapp, signed_in.isActiveWindow)
    hold_clock(signed_in, WEDNESDAY, 14 * 60 + 7)
    yield signed_in


def key(window: NativeWindow, which: Qt.Key, mods: Qt.KeyboardModifier = NONE) -> None:
    """A key from the system, to whatever the window has focused."""
    QTest.keyClick(window.windowHandle(), which, mods)
    QApplication.processEvents()
