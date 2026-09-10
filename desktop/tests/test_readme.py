from __future__ import annotations

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
    assert "Windows protected your PC" in text
    assert "SmartScreen" in text
    assert "icuuc" in text
    assert "Create account" in text
    assert "@WEB_VERSION@" in text


def test_render_inserts_the_hosted_url_or_says_none_is_online() -> None:
    assert render("X @WEB_VERSION@ Y", "") == f"X {OFFLINE} Y"
    assert "https://example.test/app" in render("@WEB_VERSION@", "https://example.test/app")
    assert render("@WEB_VERSION@", "https://example.test/app") == ONLINE.format(url="https://example.test/app")


def test_github_release_body_leads_with_download_labels() -> None:
    text = (ROOT / "docs/github-release.md").read_text(encoding="utf-8")
    assert "## Download for Windows" in text
    assert "FlexWeek-Windows-x64.zip" in text
    assert "FlexWeek-Linux-x86_64.tar.gz" in text
    assert "glibc 2.38" in text
    assert "libxcb-cursor" in text
    assert "OpenGL or EGL" in text
