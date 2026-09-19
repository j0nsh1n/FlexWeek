"""Native `--smoke-test` against a real local API, with no Chromium."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from desktop.main import PAINTED_MIN_COLORS
    from desktop.server import LocalServer


def run_smoke(tmp_path: Path, **extra: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    report = tmp_path / "smoke.json"
    (tmp_path / "tmp").mkdir()
    env = {
        **os.environ,
        "TMPDIR": str(tmp_path / "tmp"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
        **extra,
    }
    for name in ("FLEXWEEK_ORIGIN", "FLEXWEEK_DESKTOP_ORIGIN"):
        if name not in extra:
            env.pop(name, None)
    result = subprocess.run(
        [sys.executable, "-m", "desktop.main", "--smoke-test", str(report)],
        env=env,
        capture_output=True,
        text=True,
        timeout=150,
        check=False,
    )
    assert report.exists(), result.stdout + result.stderr
    return result, json.loads(report.read_text())


def test_smoke_mode_passes_once_setup_solve_paints_the_week(tmp_path: Path) -> None:
    result, report = run_smoke(tmp_path)
    assert result.returncode == 0, report
    assert report["ok"] is True
    assert report["stage"] == "week shown after setup Solve"
    assert int(report.get("block_count") or 0) >= 1
    assert cast(int, report["painted_colors"]) >= PAINTED_MIN_COLORS
    assert report["window_visible"] is True
    assert report["window_icon_loaded"] is True
    assert not (tmp_path / "data").exists() or not any((tmp_path / "data").rglob("flexweek.db"))
    assert list((tmp_path / "tmp").glob("flexweek-smoke-*")) == []


def test_smoke_mode_makes_no_account_on_a_hosted_server(tmp_path: Path) -> None:
    server = LocalServer(tmp_path / "hosted.db")
    origin = server.start()
    try:
        result, report = run_smoke(tmp_path, FLEXWEEK_DESKTOP_ORIGIN=origin)
    finally:
        server.stop()
    assert result.returncode == 0, report
    assert report["stage"] == "first screen shown"
    with sqlite3.connect(tmp_path / "hosted.db") as database:
        assert database.execute("SELECT COUNT(*) FROM users").fetchone() == (0,)


def test_smoke_mode_fails_when_the_page_cannot_load(tmp_path: Path) -> None:
    result, report = run_smoke(tmp_path, FLEXWEEK_DESKTOP_ORIGIN="http://127.0.0.1:9")
    assert result.returncode == 1
    assert report["ok"] is False
    assert report["stage"] == "page failed to load"
