"""A release archive is unpacked only inside its own folder, whatever its checksum says."""

from __future__ import annotations

import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

from desktop.tests.updater.support import make_tarball

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from desktop.native.updater import _safe_extract


def test_an_archive_that_would_escape_its_folder_is_refused(tmp_path: Path) -> None:
    """A verified checksum proves the bytes came from the release, not that the archive is sane."""
    archive = tmp_path / "evil.tar.gz"
    victim = tmp_path / "outside.txt"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("../outside.txt")
        payload = b"escaped"
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))
    destination = tmp_path / "unpack"
    destination.mkdir()
    with tarfile.open(archive) as opened, pytest.raises(tarfile.TarError):
        _safe_extract(opened, destination)
    assert not victim.exists()


def test_an_archive_linking_outside_its_folder_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("escape")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../etc/passwd"
        tar.addfile(member)
    destination = tmp_path / "unpack"
    destination.mkdir()
    with tarfile.open(archive) as opened, pytest.raises(tarfile.TarError):
        _safe_extract(opened, destination)


def test_a_normal_release_archive_unpacks(tmp_path: Path) -> None:
    archive = make_tarball(tmp_path / "src", "FlexWeek", {"FlexWeek": "binary", "README.txt": "hi"})
    destination = tmp_path / "unpack"
    destination.mkdir()
    with tarfile.open(archive) as opened:
        _safe_extract(opened, destination)
    assert (destination / "FlexWeek" / "FlexWeek").read_text() == "binary"
