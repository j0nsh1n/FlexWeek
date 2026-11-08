"""What the sync tests share: a sync service on loopback only (no test reaches the network relay), a
second device standing in for the phone, and a window given a sync host.

A test module loads the fixtures with `pytest_plugins = ["desktop.tests.sync.support"]`."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from flexweek_engine import SyncService
from PySide6.QtWidgets import QLabel, QWidget

from backend.storage import initialize
from desktop.native import devices
from desktop.native.devices import DevicesPanel, SyncHost
from desktop.native.window import NativeWindow
from desktop.tests import light_app
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, still  # noqa: F401

# The light app's fixture, passed on so a module that loads this one has it.
open_light = light_app.open_light
PHONE_NAME = "Pixel"
PAIR_DEADLINE_MS = 20_000
SCAN_MS = 1000


def loopback_service(database: Path, name: str = "Desk", scan_ms: int | None = SCAN_MS) -> SyncService:
    """A sync service for `database` that listens on 127.0.0.1 only and uses no relay."""
    key = database.parent / "sync" / "device.key"
    key.parent.mkdir(parents=True, exist_ok=True)
    if scan_ms is None:
        return SyncService.start(str(database), str(key), name, True, "127.0.0.1:0")
    return SyncService.start(str(database), str(key), name, True, "127.0.0.1:0", scan_ms)


def attach_sync(window: NativeWindow, host: SyncHost) -> None:
    """Gives a window that was opened without a sync host the one a launch would have given it:
    NativeWindow's constructor takes it, the light app does not."""
    window.session.use_sync_host(host)
    window._sync_host = host
    host.setParent(window)
    host.started.connect(window._sync_started)
    if host.service is not None:
        window._sync_started(host.service)


def stop_sync_timer(window: NativeWindow) -> None:
    """The window's once-a-second look at its service ends, so the service can stop under it."""
    window._sync_timer.stop()


def light_database(tmp_path: Path) -> Path:
    """The database file a light window opened from `open_light` runs on (the first window of the test)."""
    database = tmp_path / "window-0" / "flexweek.db"
    assert database.exists(), "the light app keeps its first window's database here"
    return database


@pytest.fixture()
def light_desk(open_light: Callable[..., NativeWindow], tmp_path: Path) -> Iterator[NativeWindow]:
    """A signed-in light window whose sync service works on the window's own database."""
    window = open_light()
    database = light_database(tmp_path)
    service = loopback_service(database)
    host = SyncHost(database)
    host.service = service
    attach_sync(window, host)
    try:
        yield window
    finally:
        stop_sync_timer(window)
        service.stop()


@pytest.fixture()
def lazy_light_desk(
    open_light: Callable[..., NativeWindow],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[NativeWindow, SyncHost, list[Path]]]:
    """A signed-in light window with no sync service yet. Starting one is counted, and it starts on
    loopback only."""
    window = open_light()
    database = light_database(tmp_path)
    started: list[Path] = []

    def loopback_start(path: Path) -> SyncService:
        started.append(path)
        return loopback_service(path)

    monkeypatch.setattr(devices, "start_service", loopback_start)
    host = SyncHost(database)
    attach_sync(window, host)
    try:
        yield window, host, started
    finally:
        stop_sync_timer(window)
        host.stop()


@pytest.fixture()
def phone(tmp_path: Path) -> Iterator[SyncService]:
    """A second device on loopback with its own empty database: the phone."""
    database = tmp_path / "phone" / "flexweek.db"
    database.parent.mkdir()
    initialize(database)
    made = loopback_service(database, PHONE_NAME, None)
    yield made
    made.stop()


def devices_panel(window: NativeWindow) -> DevicesPanel:
    window._open_settings()
    still(window)
    panel = window._settings.findChild(DevicesPanel)
    assert panel is not None, "Settings has a Devices card"
    return panel


def listed_phones(panel: DevicesPanel) -> list[str]:
    return [label.text() for label in panel.findChildren(QLabel, "phoneName")]


def label_texts(parent: QWidget) -> list[str]:
    return [label.text() for label in parent.findChildren(QLabel)]


def pair_a_phone(window: NativeWindow, phone: SyncService) -> DevicesPanel:
    """Pairs `phone` by passing it the pairing payload the sheet holds, as scanning its code would."""
    panel = devices_panel(window)
    panel.pair_button.click()
    sheet = panel.dialog
    code = sheet.findChild(QLabel, "pairCode")
    wait_until(None, lambda: re.fullmatch(r"\d{4} \d{4}", code.text()) is not None)
    text = sheet._qr_payload
    assert text.startswith("flexweek://pair/2?c=" + code.text().replace(" ", ""))
    phone.pair_from_qr(text, PAIR_DEADLINE_MS)
    wait_until(None, lambda: listed_phones(panel) == [PHONE_NAME])
    return panel


class GenerationProxy:
    """The real service, with a generation the test can raise: a phone's batch is not needed to show
    what the window does when one arrives."""

    def __init__(self, real: SyncService) -> None:
        self.real = real
        self.raised = 0

    def generation(self) -> int:
        return self.real.generation() + self.raised

    def __getattr__(self, name: str) -> object:
        return getattr(self.real, name)
