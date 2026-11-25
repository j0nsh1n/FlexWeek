"""A client freed while a worker is still answering for it: the answer goes nowhere and nothing crashes.
The session's workers (engine/app/src/session/frame.rs) wake the window through one courier that lives as
long as the program, so a worker never holds the last reference to a Qt object (devices.py met that crash
when it did). Each request's work asks the host for randomness first, which these tests hold."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import secrets
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from desktop.native import client as client_module
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import database, qapp  # noqa: F401

# The session's workers (frame.rs WORKERS).
WORKERS = 4


def test_a_client_freed_mid_request_gets_no_answer_and_the_app_carries_on(
    qapp: QApplication, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started, go_on = threading.Event(), threading.Event()

    def slow() -> object:
        started.set()
        go_on.wait(10)
        return secrets

    # The worker's wake for the freed client: once it has come, the answer is ready and on its way.
    woke = threading.Event()
    wake = client_module._wake

    def watched(key: int) -> None:
        wake(key)
        woke.set()

    monkeypatch.setattr(client_module.HOST, "entropy", slow)
    monkeypatch.setattr(client_module, "_wake", watched)
    client = client_module.NativeClient(database)
    landed: list[object] = []
    client.request("GET", "/api/health", None, landed.append, landed.append)
    assert started.wait(5)
    client.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(client)
    go_on.set()
    assert woke.wait(5), "the worker never woke the window"
    # The wake is a queued call on the window's thread: deliver it, then look.
    QCoreApplication.sendPostedEvents()
    qapp.processEvents()
    assert landed == [], "an answer reached a client that was gone"
    # The workers carry on: a new client is answered.
    monkeypatch.undo()
    again = client_module.NativeClient(database)
    answered: list[object] = []
    again.request("GET", "/api/health", None, answered.append, answered.append)
    wait_until(qapp, lambda: bool(answered))
    assert isinstance(answered[0], dict), answered
    assert landed == []


def test_every_client_shares_one_bounded_set_of_workers(
    qapp: QApplication, database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Six clients each asking at once are answered by at most WORKERS threads, not a set each."""
    go_on = threading.Event()
    lock = threading.Lock()
    answering = [0]

    def held() -> object:
        with lock:
            answering[0] += 1
        go_on.wait(10)
        return secrets

    monkeypatch.setattr(client_module.HOST, "entropy", held)
    clients = [client_module.NativeClient(database) for _ in range(6)]
    try:
        for each in clients:
            each.request("GET", "/api/health", None, lambda _answer: None, lambda _error: None)
        wait_until(qapp, lambda: answering[0] >= WORKERS)
        for _ in range(20):
            qapp.processEvents()
        assert answering[0] == WORKERS, "more requests ran at once than there are workers"
    finally:
        go_on.set()
        wait_until(qapp, lambda: all(not each._waiting for each in clients))
        for each in clients:
            each.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
