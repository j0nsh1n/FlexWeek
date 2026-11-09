"""Garbage is collected on the window's thread only, never on the local server's."""

from __future__ import annotations

import gc
import os
import threading

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from desktop.native.collector import TICK_MS, WindowThreadCollector


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(["flexweek-collector-test"])


class Remembers:
    """Notes which thread freed it."""

    freed_on: list[str] = []

    def __init__(self) -> None:
        self.me = self

    def __del__(self) -> None:
        Remembers.freed_on.append(threading.current_thread().name)


def _busy_server_thread() -> None:
    # Enough container allocations to pass the young generation's threshold several times over.
    junk = [[index] for index in range(gc.get_threshold()[0] * 20)]
    del junk


def test_garbage_left_by_the_window_is_freed_on_the_window_thread(qapp: QApplication) -> None:
    gc.enable()
    collector = WindowThreadCollector()
    try:
        Remembers.freed_on.clear()
        Remembers()
        server = threading.Thread(target=_busy_server_thread, name="flexweek-server")
        server.start()
        server.join()
        loop = QEventLoop()
        QTimer.singleShot(TICK_MS * 3, loop.quit)
        loop.exec()
        assert Remembers.freed_on == [threading.main_thread().name]
        assert not gc.isenabled()
    finally:
        collector.deleteLater()
        gc.disable()
        gc.collect()
