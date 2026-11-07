"""What the updater tests share: a release archive to unpack and a download the updater made."""

from __future__ import annotations

import tarfile
from pathlib import Path


def make_tarball(path: Path, root_name: str, files: dict[str, str]) -> Path:
    """A release archive holding `files` under one top folder, written under `path`."""
    staging = path / "build"
    (staging / root_name).mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        file_path = staging / root_name / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(text)
    archive = path / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging / root_name, arcname=root_name)
    return archive


def a_download(temp: Path, name: str = "flexweek-update-abc123") -> Path:
    """A downloaded package inside a folder of the kind the updater makes for one."""
    folder = temp / name
    folder.mkdir()
    package = folder / "FlexWeek.AppImage"
    package.write_bytes(b"new")
    return package
