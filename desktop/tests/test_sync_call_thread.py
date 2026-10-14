"""A sync call's answer object is freed, and on the window's thread, never on the worker that ran the
call. Before 1.0.0 each call left one behind for good, and when the collector ran on the worker it
freed one there while the window's thread was using it (1.0.0 gate segfault)."""

from __future__ import annotations

import gc
import importlib.util
import os
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="needs PySide6")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QCoreApplication, QEvent, QObject
    from PySide6.QtWidgets import QApplication

    from desktop.native import devices


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(["flexweek-sync-call-test"])


def test_the_answer_is_freed_on_the_window_thread(qapp: QApplication, monkeypatch) -> None:
    freed_on: list[str] = []

    class Answer(devices._Answer):
        def __del__(self) -> None:
            freed_on.append(threading.current_thread().name)

    monkeypatch.setattr(devices, "_Answer", Answer)
    owner = QObject()
    got: list[object] = []
    devices.run_off_ui(owner, lambda: time.sleep(0.05) or "done", lambda result, _problem: got.append(result))
    deadline = time.monotonic() + 5
    while (not got or devices._IN_FLIGHT or not freed_on) and time.monotonic() < deadline:
        qapp.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        time.sleep(0.01)
    assert got == ["done"]
    assert freed_on == [threading.main_thread().name]
