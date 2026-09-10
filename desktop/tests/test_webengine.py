"""Run real WebEngine integration checks in isolated processes and profiles."""

from __future__ import annotations

import importlib.util
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
    ["accounts", "calendar", "completion", "phase6", "phase7", "popup", "navigation", "download", "tray"],
)
def test_webengine(case: str, tmp_path: Path) -> None:
    env = {
        **os.environ,
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
        "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-gpu",
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
