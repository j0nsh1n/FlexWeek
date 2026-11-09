"""The Devices card and the pairing sheet ignore an answer that arrives after they were deleted, and
Cancel closes the sheet without waiting for the phone side to finish."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from flexweek_engine import SyncService
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid

from desktop.native import devices
from desktop.native.devices import DevicesPanel, PairDialog, SyncHost
from desktop.native.window import NativeWindow
from desktop.tests.sync.support import devices_panel
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free

pytest_plugins = ["desktop.tests.sync.support"]


@pytest.mark.parametrize("callback", ["refresh", "started", "pairing", "synced"])
def test_a_deleted_devices_card_ignores_late_callbacks(
    qapp: QApplication, tmp_path: Path, callback: str
) -> None:
    panel = DevicesPanel(SyncHost(tmp_path / "late.db"), lambda: 1)
    delete(panel)
    assert not isValid(panel)
    if callback == "refresh":
        panel.refresh()
    elif callback == "started":
        panel._service_started(None)
    elif callback == "pairing":
        panel._pairing(None, 1)
    else:
        panel._synced(None, RuntimeError("late sync"))


def test_a_deleted_pairing_sheet_ignores_a_late_timer(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(devices, "run_off_ui", lambda *args: None)
    sync = Mock(spec=SyncService)
    parent = QWidget()
    dialog = PairDialog(parent, sync, 1)
    delete(parent)
    assert not isValid(dialog)
    dialog._tick()
    pending = []
    monkeypatch.setattr(devices, "run_off_ui", lambda owner, work, done: pending.append(work))
    dialog._made({"display_code": "1234 5678"}, None)
    sync.pair_status.assert_not_called()
    assert len(pending) == 1
    pending[0]()
    sync.pair_cancel.assert_called_once_with()


def test_cancel_closes_before_a_slow_pair_cancel_finishes(qapp: QApplication) -> None:
    held = threading.Event()
    finished = threading.Event()
    sync = Mock(spec=SyncService)

    def slow_cancel() -> None:
        held.wait(5)
        finished.set()

    sync.pair_cancel.side_effect = slow_cancel
    parent = QWidget()
    dialog = PairDialog(parent, sync, 1)
    dialog.reject()

    assert not finished.is_set(), "Cancel returned while the phone side was still working"
    assert not dialog.isVisible()
    held.set()
    assert finished.wait(5)
    wait_until(qapp, lambda: not devices._IN_FLIGHT)
    free(parent)


def test_settings_can_close_before_the_pairing_service_starts(
    qapp: QApplication,
    lazy_light_desk: tuple[NativeWindow, SyncHost, list[Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _host, _started = lazy_light_desk
    panel = devices_panel(window)
    pending = []
    monkeypatch.setattr(devices, "run_off_ui", lambda owner, work, done: pending.append(done))
    panel.pair_button.click()
    assert len(pending) == 1
    window._discard_settings_page()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(panel)
    pending[0](None, None)
    assert window._settings is None
