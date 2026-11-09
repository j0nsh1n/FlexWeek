"""The version the app reports is the one the changelog announced."""

from __future__ import annotations

import re
from pathlib import Path

from desktop.native.version import VERSION


def test_the_version_here_is_the_one_the_changelog_announced() -> None:
    """The installers take their version from the git tag. If this constant drifts from the
    changelog, a released build reports the wrong version and never sees itself as out of date."""
    changelog = (Path(__file__).parents[3] / "CHANGELOG.md").read_text(encoding="utf-8")
    # A version still being written is headed "- Unreleased" and is not announced yet.
    headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\](?! - Unreleased)", changelog, flags=re.M)
    assert headings, "no released version in the changelog"
    assert headings[0] == VERSION, f"version.py says {VERSION}, changelog says {headings[0]}"
