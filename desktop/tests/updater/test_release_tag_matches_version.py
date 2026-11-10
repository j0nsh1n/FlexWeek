"""A release tag, the app's VERSION and the phone's versionName say the same number, and the
release workflow refuses to build when they do not (a v1.3.0 tag on a 1.2.0 app is offered its own
release as an update for ever)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from desktop.native.version import CHANNEL, VERSION

ROOT = Path(__file__).resolve().parents[3]
CHECK = ROOT / "scripts" / "check_release_tag.py"
WORKFLOW = ROOT / ".github/workflows/release-windows.yml"
STEP = "Check the tag matches the version"


def run_check(tmp_path: Path, tag: str, *, version: str = "1.3.0", channel: str = "release"):
    version_file = tmp_path / "version.py"
    version_file.write_text(f'VERSION = "{version}"\n# stamped\nCHANNEL = "{channel}"\n', encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-I", str(CHECK), "--tag", tag, "--version-file", str(version_file)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_phone_version_name_is_the_app_version() -> None:
    gradle = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    names = re.findall(r'^\s*versionName = "([^"]+)"', gradle, flags=re.M)
    assert names == [VERSION]


def test_the_checked_in_channel_is_release() -> None:
    assert CHANNEL == "release"


def test_a_tag_equal_to_the_version_passes(tmp_path: Path) -> None:
    done = run_check(tmp_path, "v1.3.0")
    assert done.returncode == 0, done.stderr


def test_a_tag_that_differs_from_the_version_fails_and_names_both(tmp_path: Path) -> None:
    done = run_check(tmp_path, "v1.3.1")
    assert done.returncode != 0
    assert "v1.3.1" in done.stderr and "1.3.0" in done.stderr


def test_a_tag_that_is_not_a_plain_release_number_fails(tmp_path: Path) -> None:
    for tag in ("1.3.0", "v1.3", "v1.3.0-rc1", "dev", "v1.3.0.202611040300"):
        assert run_check(tmp_path, tag).returncode != 0, tag


def test_a_developer_channel_fails_even_when_the_numbers_agree(tmp_path: Path) -> None:
    done = run_check(tmp_path, "v1.3.0", channel="dev")
    assert done.returncode != 0
    assert "CHANNEL" in done.stderr


def test_a_run_without_a_tag_checks_only_the_channel(tmp_path: Path) -> None:
    assert run_check(tmp_path, "").returncode == 0
    assert run_check(tmp_path, "", channel="dev").returncode != 0


def test_a_version_file_without_a_version_fails(tmp_path: Path) -> None:
    version_file = tmp_path / "version.py"
    version_file.write_text('CHANNEL = "release"\n', encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-I", str(CHECK), "--tag", "v1.3.0", "--version-file", str(version_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode != 0


def job_steps(job: str) -> list[str]:
    """The step names of one job, in order."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  {job}:")
    names = []
    for line in lines[start + 1 :]:
        if re.match(r"^  \S", line):
            break
        found = re.match(r"^      - (?:name: (.+)|uses: (\S+))$", line)
        if found:
            names.append(found.group(1) or found.group(2))
    return names


@pytest.mark.parametrize("job", ["windows", "linux"])
def test_each_release_job_checks_the_tag_before_it_builds(job: str) -> None:
    names = job_steps(job)
    assert STEP in names, f"{job} never checks the tag"
    position = names.index(STEP)
    before = names[:position]
    assert all(name.startswith("actions/") for name in before), (job, before)
    assert position <= 2


def test_the_check_step_runs_the_script_with_the_tag_from_the_event_or_the_input() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("scripts/check_release_tag.py") == 2
    assert '--tag="$TAG"' in text and '--tag="$env:TAG"' in text
