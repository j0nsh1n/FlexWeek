"""Waiting for a picture of a design to settle, without a fixed wait."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QImage

from desktop.tests.waiting import wait_until

# Polls with nothing changed in a row before a picture counts as settled. A poll comes at least every
# few milliseconds (waiting.WAKE_MS) and the designs finish laying out on the event loop.
QUIET_POLLS = 20


def settled_image(take: Callable[[], QImage]) -> QImage:
    """`take()` again, handling events in between, until it has come out the same QUIET_POLLS times in
    a row; returns that picture."""
    last = [take()]
    quiet = [0]

    def calm() -> bool:
        now = take()
        quiet[0] = quiet[0] + 1 if now == last[0] else 0
        last[0] = now
        return quiet[0] >= QUIET_POLLS

    wait_until(None, calm, timeout=15.0, what="the picture to stop changing")
    return last[0]
