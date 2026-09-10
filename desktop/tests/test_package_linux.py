from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_package_linux_ships_readme_icon_and_checksum(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    launcher = bundle / "FlexWeek"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    output = tmp_path / "release"
    env = {**os.environ, "FLEXWEEK_WEB_URL": "https://example.test/flexweek"}
    subprocess.run(
        ["bash", str(ROOT / "desktop/package_linux.sh"), str(bundle), str(output)],
        cwd=ROOT, env=env, check=True, capture_output=True, text=True,
    )
    archive = output / "FlexWeek-Linux-x86_64.tar.gz"
    checksum = output / "FlexWeek-Linux-x86_64.tar.gz.sha256"
    assert archive.is_file()
    assert checksum.read_text(encoding="utf-8").split()[1] == "FlexWeek-Linux-x86_64.tar.gz"
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        assert "FlexWeek/FlexWeek" in names
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
