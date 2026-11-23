"""A client freed while a worker is still answering for it: the worker's answer has somewhere safe to go.
The courier that carries it is kept until the answer is made, then freed on the window's thread
(desktop/native/client.py). Freed with the client instead, a worker sending on it crashed the app."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import threading
from concurrent.futures import Future
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, SignalInstance
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from desktop.native import client as client_module
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import database, qapp  # noqa: F401


def test_a_client_freed_mid_request_keeps_its_courier_until_the_answer_is_made(
    qapp: QApplication, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started, go_on, finished = threading.Event(), threading.Event(), threading.Event()

    def slow(*_arguments: object) -> client_module.Answer:
        started.set()
        go_on.wait(10)
        finished.set()
        return client_module.Answer(200, b'{"ok": true}')

    monkeypatch.setattr(client_module, "ask", slow)
    client = client_module.NativeClient(database)
    landed: list[object] = []
    client.request("GET", "/api/health", None, landed.append, landed.append)
    courier = client._courier
    assert started.wait(5)
    client.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(client)
    # The worker is still answering: its courier is kept, not freed with the client.
    assert isValid(courier)
    assert any(kept is courier for kept, _ in client_module._RETIRED)
    go_on.set()
    assert finished.wait(5)
    wait_until(qapp, lambda: not any(kept is courier for kept, _ in client_module._RETIRED))
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(courier)
    assert landed == [], "an answer reached a client that was gone"


def test_every_client_shares_one_bounded_pool_of_workers(
    qapp: QApplication, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Six clients each asking at once are answered by at most WORKERS threads, not one pool each."""
    go_on = threading.Event()
    lock = threading.Lock()
    answering = [0]

    def held(*_arguments: object) -> client_module.Answer:
        with lock:
            answering[0] += 1
        go_on.wait(10)
        return client_module.Answer(200, b'{"ok": true}')

    monkeypatch.setattr(client_module, "ask", held)
    clients = [client_module.NativeClient(database) for _ in range(6)]
    try:
        for each in clients:
            each.request("GET", "/api/health", None, lambda _answer: None, lambda _error: None)
        wait_until(qapp, lambda: answering[0] >= client_module.WORKERS)
        for _ in range(20):
            qapp.processEvents()
        assert answering[0] == client_module.WORKERS, "more requests ran at once than the pool has workers"
    finally:
        go_on.set()
        wait_until(qapp, lambda: all(not each._waiting for each in clients))
        for each in clients:
            each.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_the_work_a_worker_runs_holds_no_qt_object(
    qapp: QApplication, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker that held the last reference to a Qt object would free it on its own thread when the work
    ends. The work it is handed holds none: only a weak reference to the courier."""
    handed: list[object] = []

    class Holding:
        def submit(self, work: object) -> Future:
            handed.append(work)
            # Already done, so the client's courier is let go as soon as the client is.
            done: Future = Future()
            done.set_result(None)
            return done

    monkeypatch.setattr(client_module, "_workers", lambda: Holding())
    client = client_module.NativeClient(database)
    try:
        client.request("GET", "/api/health", None, lambda _answer: None, lambda _error: None)
        (work,) = handed
        held = [cell.cell_contents for cell in work.__closure__ or ()]  # type: ignore[attr-defined]
        qt = [item for item in held if isinstance(item, (QObject, SignalInstance))]
        assert qt == [], f"the work holds {qt}"
    finally:
        client.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
