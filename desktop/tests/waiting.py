"""The one way a test waits: for the app's own signal, or for a condition on its state. Events are
handled the moment they arrive while it waits, so nothing waits a fixed time."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEventLoop, QTimer, SignalInstance
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QWidget

TIMEOUT_S = 8.0
# A timer that wakes the wait this often, so a condition no event announces is still seen. The
# events in between (replies, timers, paints) are handled as they come.
WAKE_MS = 5


def _run_until(done: Callable[[], bool], timeout: float) -> bool:
    """Handle events, as processEvents does at the test's own level, until `done()` or `timeout`.
    Events waiting now are handled before the first look, so what a test just did has its effect."""
    QApplication.processEvents()
    if done():
        return True
    wake = QTimer()
    wake.start(WAKE_MS)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.WaitForMoreEvents)
            if done():
                return True
    finally:
        wake.stop()
    return done()


def wait_until(
    qapp: QApplication | None,
    predicate: Callable[[], bool],
    timeout: float = TIMEOUT_S,
    what: str | Callable[[], str] = "",
) -> None:
    """Handle events until `predicate()` is true. `qapp` stays for the older call form. `what` says
    what was awaited, or is called on failure to say what was seen instead."""
    if not _run_until(predicate, timeout):
        said = what() if callable(what) else what
        raise AssertionError(f"still false after {timeout:g} s" + (f": {said}" if said else ""))


def expect(
    signal: SignalInstance, action: Callable[[], object], timeout: float = TIMEOUT_S
) -> tuple[Any, ...]:
    """Do `action` and wait for the `signal` it causes, even one emitted before `action` returns;
    returns what the signal carried."""
    carried: list[tuple[Any, ...]] = []

    def caught(*values: Any) -> None:
        carried.append(values)

    signal.connect(caught)
    try:
        action()
        if not _run_until(lambda: bool(carried), timeout):
            raise AssertionError(f"no signal after {timeout:g} s")
    finally:
        signal.disconnect(caught)
    return carried[0]


def exposed(shown: QWidget | QWindow) -> Callable[[], bool]:
    """For wait_until: whether a widget's window, or a window, is on screen (a QWidget has no isExposed;
    its window handle does, once it has one)."""

    def on_screen() -> bool:
        handle = shown if isinstance(shown, QWindow) else shown.window().windowHandle()
        return handle is not None and handle.isExposed()

    return on_screen
