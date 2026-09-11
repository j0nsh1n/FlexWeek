"""Run real WebEngine integration checks in isolated processes and profiles."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)


@pytest.mark.parametrize(
    "case",
    [
        "accounts", "calendar", "completion", "phase6", "phase7", "popup", "navigation", "download",
        "tray", "no_icon", "instance", "rookie", "system_dark",
    ],
)
def test_webengine(case: str, tmp_path: Path) -> None:
    env = {
        **os.environ,
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
        # preferredColorScheme=0 makes prefers-color-scheme report dark offscreen.
        "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu"
        + (" --blink-settings=preferredColorScheme=0" if case == "system_dark" else ""),
    }
    env.pop("FLEXWEEK_ORIGIN", None)
    env.pop("FLEXWEEK_DESKTOP_ORIGIN", None)
    result = subprocess.run(
        [sys.executable, "-m", "desktop.tests.webengine_probe", case, str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS:" in result.stdout


def run_smoke(tmp_path: Path, **extra: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    report = tmp_path / "smoke.json"
    env = {
        **os.environ,
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
        "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu",
        **extra,
    }
    for name in ("FLEXWEEK_ORIGIN", "FLEXWEEK_DESKTOP_ORIGIN"):
        if name not in extra:
            env.pop(name, None)
    result = subprocess.run(
        [sys.executable, "-m", "desktop.main", "--smoke-test", str(report)],
        env=env, capture_output=True, text=True, timeout=150, check=False,
    )
    assert report.exists(), result.stdout + result.stderr
    return result, json.loads(report.read_text())


def test_smoke_mode_passes_once_the_first_screen_shows(tmp_path: Path) -> None:
    result, report = run_smoke(tmp_path)
    assert result.returncode == 0, report
    assert report["ok"] is True
    assert report["stage"] == "first screen shown"
    assert report["window_visible"] is True
    assert report["window_icon_loaded"] is True


def test_smoke_mode_fails_when_the_page_cannot_load(tmp_path: Path) -> None:
    result, report = run_smoke(tmp_path, FLEXWEEK_DESKTOP_ORIGIN="http://127.0.0.1:9")
    assert result.returncode == 1
    assert report["ok"] is False
    assert report["stage"] == "page failed to load"
