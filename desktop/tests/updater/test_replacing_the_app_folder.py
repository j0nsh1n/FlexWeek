"""Putting a downloaded release folder in place.

This is the code that replaces the app the student already has, so the tests are mostly about what
happens when it goes wrong: a swap that fails half way, a folder that holds the student's data. In
every one of those the existing install has to survive.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from desktop.tests.updater.support import make_tarball

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from desktop.native import updater
    from desktop.native.updater import _swap_tree, apply_update, bundle_root


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


def test_the_bundle_root_of_a_tarball_install_is_the_top_folder(tmp_path: Path) -> None:
    top = tmp_path / "FlexWeek"
    (top / "app").mkdir(parents=True)
    (top / "FlexWeek").write_text("launcher")
    (top / "app" / "FlexWeek").write_text("binary")
    assert bundle_root(str(top / "app" / "FlexWeek")) == top.resolve()


def test_a_folder_named_app_without_the_launcher_is_not_climbed_out_of(tmp_path: Path) -> None:
    app_dir = tmp_path / "x" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "FlexWeek").write_text("binary")
    assert bundle_root(str(app_dir / "FlexWeek")) == app_dir.resolve()


def test_updating_a_real_tarball_layout_does_not_nest_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "FlexWeek"
    (root / "app").mkdir(parents=True)
    (root / "FlexWeek").write_text("old launcher")
    (root / "app" / "FlexWeek").write_text("old binary")
    archive = make_tarball(
        tmp_path / "src",
        "FlexWeek",
        {"FlexWeek": "new launcher", "app/FlexWeek": "new binary"},
    )
    real_bundle_root = updater.bundle_root
    monkeypatch.setattr(
        "desktop.native.updater.bundle_root",
        lambda: real_bundle_root(str(root / "app" / "FlexWeek")),
    )
    assert _swap_tree(archive) is None
    assert (root / "app" / "FlexWeek").read_text() == "new binary"
    assert (root / "FlexWeek").read_text() == "new launcher"
    assert not (root / "app" / "app").exists()


def test_a_folder_holding_the_database_is_never_swapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "FlexWeek"
    root.mkdir()
    (root / "FlexWeek").write_text("launcher")
    (root / "flexweek.db").write_text("data")
    archive = make_tarball(tmp_path / "src", "FlexWeek", {"FlexWeek": "new binary"})
    monkeypatch.setattr("desktop.native.updater.bundle_root", lambda: root)
    result = _swap_tree(archive)
    assert result is not None and "data" in result
    assert (root / "flexweek.db").read_text() == "data"
    assert not (tmp_path / "FlexWeek.old").exists()
    assert not (tmp_path / "FlexWeek.update").exists()


def test_a_copy_run_from_source_does_not_replace_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "FlexWeek"
    root.mkdir()
    (root / "keep.txt").write_text("keep")
    archive = make_tarball(tmp_path / "src", "FlexWeek", {"FlexWeek": "new binary"})
    monkeypatch.setattr("desktop.native.updater.frozen", lambda: False)
    monkeypatch.setattr("desktop.native.updater.bundle_root", lambda: root)
    result = apply_update(str(archive), kind="tarball")
    assert result is not None and "source" in result
    assert (root / "keep.txt").exists()
