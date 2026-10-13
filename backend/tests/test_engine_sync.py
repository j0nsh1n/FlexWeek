"""The Rust sync service as Python sees it: pairing by QR, removal, the key file, and error words."""

from __future__ import annotations

import re
import sqlite3
import stat
import time
from collections.abc import Iterator
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

from backend.storage import initialize

HEX_ID = re.compile(r"[0-9a-f]{64}")
PAIR_MS = 5 * 60 * 1000


def database(path: Path) -> int:
    """A database with the store's schema and one account, returns that account's id."""
    initialize(path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users(username, password_hash) VALUES ('ada', 'not-a-real-hash')")
        return db.execute("SELECT id FROM users WHERE username = 'ada'").fetchone()[0]


def service(path: Path, name: str, key_dir: Path) -> flexweek_engine.SyncService:
    return flexweek_engine.SyncService.start(
        str(path),
        str(key_dir / "device.key"),
        name,
        lan_only=True,
        bind="127.0.0.1:0",
    )


@pytest.fixture()
def desk(tmp_path: Path) -> Iterator[tuple[flexweek_engine.SyncService, int, Path]]:
    path = tmp_path / "desk" / "flexweek.db"
    path.parent.mkdir()
    user_id = database(path)
    running = service(path, "Desk", path.parent / "sync")
    yield running, user_id, path
    running.stop()


@pytest.fixture()
def phone(tmp_path: Path) -> Iterator[flexweek_engine.SyncService]:
    path = tmp_path / "phone" / "flexweek.db"
    path.parent.mkdir()
    initialize(path)
    running = service(path, "Pixel", path.parent / "sync")
    yield running
    running.stop()


def test_the_key_file_is_private_and_sits_beside_the_database(desk) -> None:
    running, _, path = desk
    key = path.parent / "sync" / "device.key"
    assert HEX_ID.fullmatch(running.device_id())
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert running.status()["listening"] is True


def test_stop_can_be_called_twice(desk) -> None:
    running, _, _ = desk
    running.stop()
    running.stop()


def test_a_code_of_the_wrong_shape_is_refused_with_its_word(phone) -> None:
    with pytest.raises(flexweek_engine.SyncError) as refused:
        phone.pair_with_code("12", [], 5000)
    assert refused.value.kind == "bad_code"


def test_removing_an_unknown_device_says_not_paired(desk) -> None:
    running, user_id, _ = desk
    with pytest.raises(flexweek_engine.SyncError) as refused:
        running.unlink(user_id, "ab" * 32, False)
    assert refused.value.kind == "not_paired"


def test_a_phone_pairs_by_qr_and_the_desktop_lists_it_then_removes_it(desk, phone) -> None:
    running, user_id, _ = desk
    offer = running.pair_start(user_id)
    assert re.fullmatch(r"\d{4} \d{4}", offer["display_code"])
    assert offer["code"] == offer["display_code"].replace(" ", "")
    assert offer["qr"].startswith("flexweek://pair?c=" + offer["code"])
    assert abs(offer["expires_at_ms"] - time.time() * 1000 - PAIR_MS) < 10_000
    waiting = running.pair_status()
    assert waiting["state"] == "waiting"
    assert waiting["tries_left"] == 3

    host = phone.pair_from_qr(offer["qr"], 20_000)
    assert host["host_device_id"] == running.device_id()
    assert host["host_name"] == "Desk"

    paired = running.pair_status()
    assert paired["state"] == "paired"
    assert paired["peer"]["device_id"] == phone.device_id()
    rows = running.peers(user_id)
    assert [(row["device_id"], row["name"], row["revoked"]) for row in rows] == [
        (phone.device_id(), "Pixel", False)
    ]

    summary = phone.sync_once(running.device_id(), 20_000)
    assert summary["exchanges"] >= 1

    running.unlink(user_id, phone.device_id(), False)
    assert running.peers(user_id)[0]["revoked"] is True
    with pytest.raises(flexweek_engine.SyncError) as removed:
        phone.sync_once(running.device_id(), 10_000)
    assert removed.value.kind == "not_paired"
