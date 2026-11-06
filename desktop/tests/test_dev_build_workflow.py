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


def _step(name: str) -> str:
    """The text of one workflow step, from its `- name:` line to the next step."""
    start = WORKFLOW.index(f"- name: {name}")
    end = WORKFLOW.find("\n      - ", start + 1)
    return WORKFLOW[start:] if end == -1 else WORKFLOW[start:end]


def test_the_dev_build_ships_only_the_tarball_and_its_checksum() -> None:
    assert "AppImage" not in WORKFLOW
    assert "packaging/make-appimage.sh" not in WORKFLOW
    create = _step("Publish developer release")
    create = create[create.index("gh release create dev") :]
    assert "dist/release/FlexWeek-Linux-x86_64.tar.gz \\" in create
    assert "dist/release/FlexWeek-Linux-x86_64.tar.gz.sha256" in create
    assert create.count("dist/release/") == 2, "only the tarball and its checksum are uploaded"


def test_the_dev_build_smokes_the_tarball_before_publishing() -> None:
    archive = _step("Smoke the packaged archive")
    assert "tar -xzf dist/release/FlexWeek-Linux-x86_64.tar.gz" in archive
    assert "dist/stage/FlexWeek/FlexWeek --smoke-test dist/packaged-smoke.json" in archive
    assert 'r.get("stage") == "week shown after setup Solve"' in archive
    helper = _step("Smoke the packaged helper in the archive")
    assert "python desktop/smoke_mcp.py dist/stage/FlexWeek/FlexWeek" in helper
    publish_idx = WORKFLOW.index("- name: Publish developer release")
    assert WORKFLOW.index("- name: Smoke the packaged archive") < publish_idx
    assert WORKFLOW.index("- name: Smoke the packaged helper in the archive") < publish_idx


def test_the_dev_release_script_starts_the_workflow_on_main() -> None:
    assert SCRIPT_PATH.is_file()
    assert (SCRIPT_PATH.stat().st_mode & 0o111) != 0, "Script must be executable"
    assert "set -euo pipefail" in SCRIPT
    assert "gh workflow run dev-build.yml --ref main" in SCRIPT
    assert "gh release create" not in SCRIPT
    # It must not claim another run's link: a run listed right after dispatch may not be this one.
    assert "gh run list" not in SCRIPT


def test_the_build_it_replaces_is_kept_under_its_commit() -> None:
    """The kept copy is tagged dev-<the old build's commit> and the old title may already name a commit."""
    assert "old_version=${old_version%% (*}" in WORKFLOW
    assert "old_sha=$(git ls-remote origin refs/tags/dev | cut -f1)" in WORKFLOW
    assert 'kept="dev-${old_sha:0:7}"' in WORKFLOW
    assert WORKFLOW.index('kept="dev-${old_sha:0:7}"') < WORKFLOW.index("gh release delete dev --cleanup-tag")


def test_the_kept_copy_is_tagged_at_this_runs_commit() -> None:
    """A new tag on the old build's commit was refused (HTTP 403) once main's workflows had changed; the kept
    copy's tag points at this run's commit and names the old one instead."""
    keep = WORKFLOW[WORKFLOW.index('gh release create "$kept"') :]
    keep = keep[: keep.index("have=$(")]
    assert '--target "$(git rev-parse HEAD)"' in keep
    assert '--target "$old_sha"' not in keep
    assert "built from $old_sha" in keep
