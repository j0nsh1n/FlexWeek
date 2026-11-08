"""The sync service starts only when a phone is linked at launch or when Pair a phone is pressed.
With none, FlexWeek opens no network endpoint and the Devices card offers Pair a phone."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from backend.storage import initialize
from desktop.native import devices
from desktop.native.devices import NO_PHONE_WORDS, PairDialog, SyncHost, linked_phone_at_launch
from desktop.native.window import NativeWindow
from desktop.tests.sync.support import (
    PHONE_NAME,
    devices_panel,
    label_texts,
    listed_phones,
    loopback_service,
)
from desktop.tests.waiting import wait_until

pytest_plugins = ["desktop.tests.sync.support"]


def database_with_phone(database: Path, revoked: int) -> None:
    """A database that has run sync once and holds one phone, removed (revoked 1) or not (0)."""
    initialize(database)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users(username, password_hash) VALUES ('ada', 'not-a-real-hash')")
    running = loopback_service(database)
    running.stop()
    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO sync_peer"
            "(user_id, peer_device_id, endpoint_id, name, paired_at, last_seen, revoked) "
            "VALUES (1, 'phone-1', 'endpoint-1', ?, '2026-10-13T00:00:00Z', NULL, ?)",
            (PHONE_NAME, revoked),
        )


def test_a_fresh_database_starts_no_sync_service_at_launch(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "flexweek.db"
    initialize(database)
    started: list[Path] = []
    monkeypatch.setattr(devices, "start_service", lambda path: started.append(path))
    host = SyncHost(database)
    host.start_if_paired()
    assert not host.starting, "no start was asked for"
    qapp.processEvents()
    assert started == []
    assert host.service is None


def test_a_database_whose_only_phone_was_removed_starts_no_service(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "flexweek.db"
    database_with_phone(database, revoked=1)
    assert linked_phone_at_launch(database) is False
    started: list[Path] = []
    monkeypatch.setattr(devices, "start_service", lambda path: started.append(path))
    host = SyncHost(database)
    host.start_if_paired()
    assert not host.starting
    qapp.processEvents()
    assert started == []


def test_a_database_with_a_linked_phone_starts_the_service_at_launch(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "flexweek.db"
    database_with_phone(database, revoked=0)
    assert linked_phone_at_launch(database) is True
    started: list[Path] = []
    monkeypatch.setattr(devices, "start_service", lambda path: started.append(path))
    host = SyncHost(database)
    host.start_if_paired()
    wait_until(qapp, lambda: started)
    assert started == [database]


def test_asking_for_the_service_twice_starts_it_once(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[tuple] = []
    monkeypatch.setattr(devices, "run_off_ui", lambda owner, work, done: starts.append((work, done)))
    host = SyncHost(tmp_path / "flexweek.db")
    host.ensure(lambda service: None)
    host.ensure(lambda service: None)
    assert len(starts) == 1, "a second ask waits for the first start instead of starting another"


def test_the_card_before_any_service_offers_pair_a_phone(
    lazy_light_desk: tuple[NativeWindow, SyncHost, list[Path]],
) -> None:
    window, host, started = lazy_light_desk
    panel = devices_panel(window)
    assert host.service is None
    assert started == []
    assert listed_phones(panel) == []
    assert NO_PHONE_WORDS in label_texts(panel)
    assert panel.pair_button.isEnabled()
    assert not panel.sync_button.isEnabled()
    assert window.sync_dot.isHidden()


def test_pressing_pair_starts_the_service_once_and_opens_the_pairing_sheet(
    lazy_light_desk: tuple[NativeWindow, SyncHost, list[Path]],
) -> None:
    window, host, started = lazy_light_desk
    panel = devices_panel(window)
    panel.pair_button.click()
    assert not panel.pair_button.isEnabled(), "Pair is off while the service starts"
    panel.pair_button.click()
    wait_until(None, lambda: isinstance(panel.dialog, PairDialog))
    assert len(started) == 1
    assert host.service is not None
    code = panel.dialog.findChild(QLabel, "pairCode")
    wait_until(None, lambda: re.fullmatch(r"\d{4} \d{4}", code.text()) is not None)
    assert not any("scan the code" in text.lower() for text in label_texts(panel.dialog))
    assert panel.dialog.findChild(QLineEdit, "pairQr") is None
    assert panel.dialog.status.text().startswith("Code works for ")
    panel.dialog.reject()
