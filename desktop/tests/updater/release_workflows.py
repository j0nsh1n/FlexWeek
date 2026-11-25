"""The release packages are built by two workflows since CI moved to Depot (2026-11-24): the Windows
installers on GitHub Actions, the Linux downloads on Depot CI. Tests that check both jobs read them
as one text."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WINDOWS = ROOT / ".github/workflows/release-windows.yml"
LINUX = ROOT / ".depot/workflows/release-linux.yml"


def release_text() -> str:
    return WINDOWS.read_text(encoding="utf-8") + "\n" + LINUX.read_text(encoding="utf-8")
