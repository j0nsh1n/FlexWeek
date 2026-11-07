"""The Linux tarball: what it ships, how its launcher hands arguments to the helper, and that it is
not made without the helper."""

from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_package_linux_ships_readme_icon_and_checksum(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    launcher = bundle / "FlexWeek"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    helper = bundle / "flexweek-mcp"
    helper.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\n', encoding="utf-8")
    helper.chmod(0o755)
    output = tmp_path / "release"
    env = {**os.environ, "FLEXWEEK_WEB_URL": "https://example.test/flexweek"}
    subprocess.run(
        ["bash", str(ROOT / "desktop/package_linux.sh"), str(bundle), str(output)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    archive = output / "FlexWeek-Linux-x86_64.tar.gz"
    checksum = output / "FlexWeek-Linux-x86_64.tar.gz.sha256"
    assert archive.is_file()
    assert checksum.read_text(encoding="utf-8").split()[1] == "FlexWeek-Linux-x86_64.tar.gz"
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        assert "FlexWeek/FlexWeek" in names
        assert "FlexWeek/app/flexweek-mcp" in names
        assert "FlexWeek/README.txt" in names
        assert "FlexWeek/flexweek.png" in names
        assert "FlexWeek/flexweek.desktop" in names
        assert "FlexWeek/install-menu-entry.sh" in names
        assert "FlexWeek/LICENSE.txt" in names
        readme = tar.extractfile("FlexWeek/README.txt")
        assert readme is not None
        text = readme.read().decode("utf-8")
        member = tar.getmember("FlexWeek/FlexWeek")
    assert "https://example.test/flexweek" in text
    assert "@WEB_VERSION@" not in text
    assert member.mode & 0o111


def test_package_launcher_sends_mcp_arguments_to_the_helper(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    app = bundle / "FlexWeek"
    app.write_text('#!/bin/sh\nprintf "APP\\n"\n', encoding="utf-8")
    app.chmod(0o755)
    helper = bundle / "flexweek-mcp"
    helper.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\n', encoding="utf-8")
    helper.chmod(0o755)
    output = tmp_path / "release"
    subprocess.run(
        ["bash", str(ROOT / "desktop/package_linux.sh"), str(bundle), str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    extracted = tmp_path / "extracted"
    with tarfile.open(output / "FlexWeek-Linux-x86_64.tar.gz") as tar:
        tar.extractall(extracted)
    result = subprocess.run(
        [str(extracted / "FlexWeek/FlexWeek"), "--mcp", "--read-only", "--data-dir", "/path with spaces"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert result.stdout == "--read-only\n--data-dir\n/path with spaces\n"
    assert "APP" not in result.stdout


def test_packaging_without_mcp_helper_fails_without_an_archive(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    launcher = bundle / "FlexWeek"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    output = tmp_path / "release"
    result = subprocess.run(
        ["bash", str(ROOT / "desktop/package_linux.sh"), str(bundle), str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0, "packaging without flexweek-mcp must fail"
    assert "flexweek-mcp is missing" in result.stderr
    assert not (output / "FlexWeek-Linux-x86_64.tar.gz").exists()
