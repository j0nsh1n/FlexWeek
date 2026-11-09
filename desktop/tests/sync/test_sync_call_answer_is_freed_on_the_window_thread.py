"""A sync call's answer object is freed, and on the window's thread, never on the worker that ran the
call: each call once left one behind for good, and when the collector ran on the worker it freed one
there while the window's thread was using it (a crash)."""

from __future__ import annotations

import gc
import threading

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QApplication

from desktop.native import devices
from desktop.tests.waiting import wait_until

pytest_plugins = ["desktop.tests.window_support"]


def collect_what_is_freeable() -> None:
    """What the window's event loop and the collector would do between two turns."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def test_the_answer_is_freed_on_the_window_thread(qapp: QApplication, monkeypatch) -> None:
    freed_on: list[str] = []

    class Answer(devices._Answer):
        def __del__(self) -> None:
            freed_on.append(threading.current_thread().name)

    monkeypatch.setattr(devices, "_Answer", Answer)
    owner = QObject()
    got: list[object] = []
    devices.run_off_ui(owner, lambda: "done", lambda result, _problem: got.append(result))

    def everything_let_go() -> bool:
        collect_what_is_freeable()
        return bool(got) and not devices._IN_FLIGHT and bool(freed_on)

    wait_until(qapp, everything_let_go, what=lambda: f"got={got} in flight={len(devices._IN_FLIGHT)}")
    assert got == ["done"]
    assert freed_on == [threading.main_thread().name]


def test_closing_the_caller_while_its_call_runs_frees_nothing_under_the_worker(qapp: QApplication) -> None:
    """Pair a phone closed while its call ran deleted the call's answer with it, while the worker was
    emitting on it: a segfault in the gate. The answer outlives its caller; nothing is told."""
    owner = QObject()
    started = threading.Event()
    release = threading.Event()
    got: list[object] = []

    def work() -> str:
        started.set()
        release.wait(5)
        return "late"

    devices.run_off_ui(owner, work, lambda result, _problem: got.append(result))
    assert started.wait(5)
    ((answer, _worker),) = list(devices._IN_FLIGHT)
    owner.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert shiboken6.isValid(answer), "the answer went with its caller"
    release.set()

    def worker_has_ended() -> bool:
        collect_what_is_freeable()
        return not devices._IN_FLIGHT

    wait_until(qapp, worker_has_ended, what="the worker's call to end")
    assert got == [] and not devices._IN_FLIGHT
