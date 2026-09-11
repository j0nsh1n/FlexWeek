from __future__ import annotations

import re
from pathlib import Path

from desktop.readme import OFFLINE, ONLINE, render

ROOT = Path(__file__).resolve().parents[2]


def test_linux_readme_names_the_machine_requirements() -> None:
    text = (ROOT / "desktop/linux/README.txt").read_text(encoding="utf-8")
    assert "glibc 2.38" in text
    assert "libxcb-cursor" in text
    assert "OpenGL or EGL" in text
    assert "@WEB_VERSION@" in text
    assert "Create account" in text


def test_windows_readme_covers_smartscreen_and_icu_by_the_os() -> None:
    text = (ROOT / "desktop/windows/README.txt").read_text(encoding="utf-8")
    start = text.split("Install and start FlexWeek\n--------------------------\n", 1)[1]
    assert start.startswith("1. Run FlexWeek-Windows-x64-Setup.exe.")
    assert "FlexWeek-Windows-x64.msi" in text
    assert "Start menu" in text
    assert ".zip" not in text and "app/" not in text
    assert "Windows protected your PC" in text
    assert "SmartScreen" in text
    assert "icuuc" in text
    assert "Create account" in text
    assert "@WEB_VERSION@" in text


def test_readme_screenshots_exist_and_none_sit_unused() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    shown = re.findall(r"!\[[^\]]+\]\((docs/images/[^)]+)\)", text)
    assert shown, "README shows no screenshots"
    missing = [path for path in shown if not (ROOT / path).is_file()]
    assert missing == []
    on_disk = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs/images").iterdir())
    assert sorted(set(shown)) == on_disk


def test_render_inserts_the_hosted_url_or_says_none_is_online() -> None:
    assert render("X @WEB_VERSION@ Y", "") == f"X {OFFLINE} Y"
    assert "https://example.test/app" in render("@WEB_VERSION@", "https://example.test/app")
    assert render("@WEB_VERSION@", "https://example.test/app") == ONLINE.format(url="https://example.test/app")


APPIMAGE_EXTRACT = (
    "`chmod +x FlexWeek-x86_64.AppImage && ./FlexWeek-x86_64.AppImage --appimage-extract`, "
    "which unpacks a `squashfs-root` folder, then run `./squashfs-root/AppRun`. "
    "Without FUSE, the tarball above is the reliable choice."
)


def test_readme_and_release_body_tell_people_what_to_do_without_fuse() -> None:
    for name in ("README.md", "docs/github-release.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "(missing FUSE)" in text, name
        assert APPIMAGE_EXTRACT in text, name
        assert "open FlexWeek.exe" not in text, name


def test_readme_and_release_body_offer_the_windows_installers_not_a_zip() -> None:
    for name in ("README.md", "docs/github-release.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "`FlexWeek-Windows-x64-Setup.exe`" in text, name
        assert "`FlexWeek-Windows-x64.msi`" in text, name
        assert "Start menu" in text, name
        assert "FlexWeek-Windows-x64.zip" not in text, name


def test_github_release_body_leads_with_download_labels() -> None:
    text = (ROOT / "docs/github-release.md").read_text(encoding="utf-8")
    assert "FlexWeek-x86_64.AppImage.sha256" in text
    assert "## Download for Windows\n`FlexWeek-Windows-x64-Setup.exe`" in text
    assert "FlexWeek-Windows-x64-Setup.exe.sha256" in text
    assert "FlexWeek-Windows-x64.msi.sha256" in text
    assert "FlexWeek-Linux-x86_64.tar.gz" in text
    assert "glibc 2.38" in text
    assert "libxcb-cursor" in text
    assert "OpenGL or EGL" in text
