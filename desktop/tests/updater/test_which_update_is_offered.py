"""What the wrapper around the update rules decides: where this copy is installed, and that the
release already running is never offered. The rest of the rules are tested in
engine/engine/tests/desk_update.rs."""

from __future__ import annotations

from desktop.native.update import available, install_kind
from desktop.native.version import VERSION


def test_the_executable_path_is_resolved_before_it_is_compared_with_the_mount() -> None:
    """The original resolved both paths. `..` steps out of the mount, so this copy is not the image."""
    assert (
        install_kind(
            "linux",
            appimage="/x/FlexWeek.AppImage",
            appdir="/tmp/.mount_fw",
            executable="/tmp/.mount_fw/../elsewhere/FlexWeek",
        )
        == "tarball"
    )


def _release(tag: str) -> dict:
    name = "FlexWeek-Linux-x86_64.tar.gz"
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": name, "browser_download_url": f"https://example.invalid/{tag}/{name}"},
            {
                "name": name + ".sha256",
                "browser_download_url": f"https://example.invalid/{tag}/{name}.sha256",
            },
        ],
    }


def test_the_release_already_running_is_never_offered() -> None:
    """The 0.17.2 audit saw the prompt offer the version that was running. A release is offered only
    when its tag is newer than this build: the same tag, with or without its v, is nothing."""
    assert available(_release(VERSION), "tarball") is None
    assert available(_release("v" + VERSION), "tarball") is None
    assert available(_release("99.0.0"), "tarball") is not None
