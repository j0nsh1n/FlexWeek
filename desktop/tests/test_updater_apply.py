"""Putting a downloaded release in place.

This is the code that replaces the app the student already has, so the tests are mostly about what
happens when it goes wrong: a directory that cannot be written, an archive that would escape its
folder, a swap that fails half way. In every one of those the existing install has to survive.
"""

from __future__ import annotations

import importlib.util
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from desktop.native.updater import _safe_extract, _swap_file, _swap_tree, writable


def make_tarball(path: Path, root_name: str, files: dict[str, str]) -> Path:
    staging = path / "build"
    (staging / root_name).mkdir(parents=True)
    for name, text in files.items():
        (staging / root_name / name).write_text(text)
    archive = path / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(staging / root_name, arcname=root_name)
    return archive


def test_a_file_swap_leaves_the_new_bytes_in_the_old_place(tmp_path: Path) -> None:
    target = tmp_path / "FlexWeek.AppImage"
    target.write_bytes(b"old")
    source = tmp_path / "downloaded"
    source.write_bytes(b"new")
    assert _swap_file(source, target) is None
    assert target.read_bytes() == b"new"


def test_a_swapped_file_can_still_be_run(tmp_path: Path) -> None:
    """An AppImage that arrives without its executable bit is an AppImage that will not start."""
    target = tmp_path / "FlexWeek.AppImage"
    target.write_bytes(b"old")
    source = tmp_path / "downloaded"
    source.write_bytes(b"new")
    _swap_file(source, target)
    assert target.stat().st_mode & 0o111


def test_a_file_swap_leaves_nothing_behind(tmp_path: Path) -> None:
    target = tmp_path / "FlexWeek.AppImage"
    target.write_bytes(b"old")
    source = tmp_path / "downloaded"
    source.write_bytes(b"new")
    _swap_file(source, target)
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".new")] == []


def test_a_directory_that_cannot_be_written_is_reported_not_forced(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    target = locked / "FlexWeek.AppImage"
    source = tmp_path / "downloaded"
    source.write_bytes(b"new")
    if writable(locked):
        pytest.skip("running as a user that can write anywhere")
    problem = _swap_file(source, target)
    assert problem is not None and "cannot be written" in problem


def test_a_tree_swap_replaces_the_bundle_with_the_new_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "FlexWeek"
    root.mkdir()
    (root / "FlexWeek").write_text("old binary")
    (root / "stale.txt").write_text("should not survive")
    archive = make_tarball(tmp_path / "src", "FlexWeek", {"FlexWeek": "new binary"})
    monkeypatch.setattr("desktop.native.updater.bundle_root", lambda: root)
    assert _swap_tree(archive) is None
    assert (root / "FlexWeek").read_text() == "new binary"
    assert not (root / "stale.txt").exists(), "a file dropped in the new release stayed behind"


def test_a_tree_swap_cleans_up_after_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "FlexWeek"
    root.mkdir()
    (root / "FlexWeek").write_text("old")
    archive = make_tarball(tmp_path / "src", "FlexWeek", {"FlexWeek": "new"})
    monkeypatch.setattr("desktop.native.updater.bundle_root", lambda: root)
    _swap_tree(archive)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith((".update", ".old"))]
    assert leftovers == []


def test_a_broken_archive_leaves_the_working_app_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of building beside and swapping: a failure must not leave half an app."""
    root = tmp_path / "FlexWeek"
    root.mkdir()
    (root / "FlexWeek").write_text("old binary")
    broken = tmp_path / "broken.tar.gz"
    broken.write_bytes(b"not a tarball at all")
    monkeypatch.setattr("desktop.native.updater.bundle_root", lambda: root)
    problem = _swap_tree(broken)
    assert problem is not None
    assert (root / "FlexWeek").read_text() == "old binary"


def test_an_archive_that_would_escape_its_folder_is_refused(tmp_path: Path) -> None:
    """A verified checksum proves the bytes came from the release, not that the archive is sane."""
    archive = tmp_path / "evil.tar.gz"
    victim = tmp_path / "outside.txt"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo("../outside.txt")
        payload = b"escaped"
        member.size = len(payload)
        import io

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
