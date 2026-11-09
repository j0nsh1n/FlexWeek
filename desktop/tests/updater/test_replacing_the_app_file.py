"""Putting a downloaded AppImage in place: the existing file is swapped whole, or left alone."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from desktop.native.updater import _swap_file, writable


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
    assert problem is not None and "can't be written" in problem
