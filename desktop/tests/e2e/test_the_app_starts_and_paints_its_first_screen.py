"""Native `--smoke-test` as the app runs, with no server and no Chromium."""

from __future__ import annotations

import importlib.util
import json
import os
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


def run_smoke(
    tmp_path: Path, *arguments: str, **extra: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
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
        [sys.executable, "-m", "desktop.main", "--smoke-test", str(report), *arguments],
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
    assert report["material_ok"] is True
    assert cast(int, report["material_painted_colors"]) >= PAINTED_MIN_COLORS
    assert not (tmp_path / "data").exists() or not any((tmp_path / "data").rglob("flexweek.db"))
    assert list((tmp_path / "tmp").glob("flexweek-smoke-*")) == []
    # Started as the app starts, phone sync set up and no phone paired: no network port (None where
    # the system's socket tables cannot be read).
    assert report["listening"] in ([], None), report["listening"]


def test_the_old_hosted_server_setting_is_not_read(tmp_path: Path) -> None:
    """The hosted server is gone (decision D4): an address left in the setting changes nothing, and the
    app still opens on its own saved data."""
    result, report = run_smoke(
        tmp_path, FLEXWEEK_DESKTOP_ORIGIN="http://127.0.0.1:9", FLEXWEEK_ORIGIN="http://127.0.0.1:9"
    )
    assert result.returncode == 0, report
    assert report["stage"] == "week shown after setup Solve"


def test_a_database_asked_for_in_a_new_folder_is_made_there(tmp_path: Path) -> None:
    database = tmp_path / "new" / "folder" / "flexweek.db"
    result, report = run_smoke(tmp_path, "--database", str(database))
    assert result.returncode == 0, report
    assert database.is_file()


def test_saved_data_that_cannot_be_opened_is_named_in_the_report(tmp_path: Path) -> None:
    """A start that fails says why (a Windows install once said only that it stopped)."""
    blocked = tmp_path / "a-file-not-a-folder"
    blocked.write_text("")
    result, report = run_smoke(tmp_path, "--database", str(blocked / "flexweek.db"))
    assert result.returncode == 3
    assert report["ok"] is False
    assert str(report["stage"]).startswith("saved data did not open: ")
    assert list((tmp_path / "tmp").glob("flexweek-smoke-*")) == []
