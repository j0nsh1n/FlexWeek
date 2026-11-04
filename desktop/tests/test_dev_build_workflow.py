"""Text and structural checks on the Linux developer build workflow and helper script."""

from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github/workflows/dev-build.yml"
SCRIPT_PATH = ROOT / "scripts/dev-release.sh"

WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")


def test_the_dev_build_workflow_parses_as_valid_yaml() -> None:
    if yaml is not None:
        data = yaml.safe_load(WORKFLOW)
        assert data.get("name") == "Developer build"
        triggers = data.get("on") if "on" in data else data.get(True, {})
        assert "workflow_dispatch" in triggers


def test_the_dev_build_runs_only_by_hand() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    for forbidden in ("schedule:", "push:", "pull_request:", "release:"):
        assert forbidden not in WORKFLOW


def test_the_dev_build_is_a_prerelease_and_never_latest() -> None:
    assert "--prerelease" in WORKFLOW
    assert "--latest=false" in WORKFLOW
    matches = re.findall(r"--latest(?:=\S+)?", WORKFLOW)
    assert matches, "Expected --latest=false flag"
    assert all(m == "--latest=false" for m in matches)
    assert "gh release delete dev --cleanup-tag --yes" in WORKFLOW
    assert "gh release create dev" in WORKFLOW
    assert "gh release create nightly" not in WORKFLOW
    assert "gh release create latest" not in WORKFLOW


def test_the_dev_build_stamps_its_version_and_channel_and_checks_them() -> None:
    assert 'DEVVERSION="${BASE}.$(date -u +%Y%m%d%H%M)"' in WORKFLOW
    assert 'sed -i "s/^VERSION = \\".*\\"/VERSION = \\"$DEVVERSION\\"/" desktop/native/version.py' in WORKFLOW
    assert 'sed -i \'s/^CHANNEL = "release"/CHANNEL = "dev"/\' desktop/native/version.py' in WORKFLOW
    assert 'grep -q "VERSION = \\"$DEVVERSION\\"" desktop/native/version.py' in WORKFLOW
    assert "grep -q 'CHANNEL = \"dev\"' desktop/native/version.py" in WORKFLOW


def test_the_dev_build_ships_only_the_tarball() -> None:
    assert "AppImage" not in WORKFLOW
    assert "packaging/make-appimage.sh" not in WORKFLOW
    assert "dist/release/FlexWeek-Linux-x86_64.tar.gz" in WORKFLOW
    assert "dist/release/FlexWeek-Linux-x86_64.tar.gz.sha256" in WORKFLOW


def test_the_dev_build_smokes_the_tarball_before_publishing() -> None:
    smoke_idx = WORKFLOW.index("Smoke the packaged archive")
    smoke_mcp_idx = WORKFLOW.index("Smoke the packaged helper in the archive")
    publish_idx = WORKFLOW.index("Publish developer release")
    assert smoke_idx < publish_idx
    assert smoke_mcp_idx < publish_idx


def test_the_dev_release_script_starts_the_workflow_on_main() -> None:
    assert SCRIPT_PATH.is_file()
    assert (SCRIPT_PATH.stat().st_mode & 0o111) != 0, "Script must be executable"
    assert "set -euo pipefail" in SCRIPT
    assert "gh workflow run dev-build.yml --ref main" in SCRIPT
    assert "gh release create" not in SCRIPT
