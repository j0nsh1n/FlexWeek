"""The first phone has no sync service running yet: pairing starts one on the signed-in database."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flexweek_engine import SyncService  # type: ignore[import-untyped]
from PySide6.QtWidgets import QApplication

from desktop.native.devices import SyncHost
from desktop.server import LocalServer
from desktop.tests.logic_support import qapp, server, signed_in  # noqa: F401
from desktop.tests.waiting import wait_until

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


def test_pairing_starts_a_fresh_host(
    qapp: QApplication,
    server: LocalServer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first phone has no service running. Pairing starts that host, then asks it for a code."""
    session = signed_in(qapp, server.origin, "pair_fresh", create=True)
    account = session.account
    assert account is not None
    database = tmp_path / "flexweek.db"
    started: list[Path] = []

    def loopback_start(path: Path) -> SyncService:
        started.append(path)
        (path.parent / "sync").mkdir(parents=True, exist_ok=True)
        return SyncService.start(
            str(path),
            str(path.parent / "sync" / "device.key"),
            "Desk",
            True,
            "127.0.0.1:0",
            1000,
        )

    monkeypatch.setattr("desktop.native.devices.start_service", loopback_start)
    host = SyncHost(database)
    assert host.service is None
    session.use_sync_host(host)
    heard: list[tuple[object, Exception | None]] = []
    try:
        assert session.begin_pairing(lambda result, problem: heard.append((result, problem))) is True
        wait_until(qapp, lambda: len(heard) == 1)
        result, problem = heard[0]
        assert problem is None
        assert started == [database]
        assert isinstance(result, dict)
        assert re.fullmatch(r"\d{4} \d{4}", str(result["display_code"]))
    finally:
        host.stop()
