"""Python's garbage collector runs on whichever thread happens to allocate when its count is reached.
The local server runs on a thread of its own, so that was sometimes the server's thread, which then
freed Qt objects the window was still drawing with, and the app crashed mid-paint. Automatic
collection is switched off and the window's own thread collects from a timer instead."""

from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer

TICK_MS = 500


class WindowThreadCollector(QObject):
    """Collects on the thread that made it, which must be the one running the window."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._young = gc.get_threshold()[0]
        gc.disable()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        self._timer.start(TICK_MS)

    def tick(self) -> None:
        # Young objects every tick, which is quick. Past the usual count, generation 1, which also
        # takes the next increment of the old objects (Python 3.14).
        gc.collect(1 if gc.get_count()[0] >= self._young else 0)
