"""Packaged builds compile the native window and must not follow the retired Chromium shell."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINUX = (ROOT / "desktop/build_linux.sh").read_text(encoding="utf-8")
WINDOWS = (ROOT / "desktop/build_windows.ps1").read_text(encoding="utf-8")
FINISH = (ROOT / "desktop/finish_linux_bundle.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/release-windows.yml").read_text(encoding="utf-8")


def test_nuitka_does_not_compile_the_retired_webengine_shell() -> None:
    assert "--include-package=desktop \\" not in LINUX
    assert "'--include-package=desktop'" not in WINDOWS
    for text in (LINUX, WINDOWS):
        assert "include-package=desktop.native" in text
        assert "desktop.webengine" in text
        assert "PySide6.QtWebEngineCore" in text
        assert "noinclude-module" not in text


def test_linux_trim_survives_a_bundle_with_no_chromium_locales() -> None:
    assert '[[ -d "$BUNDLE/qtwebengine_locales" ]]' in FINISH


def test_release_jobs_fail_if_chromium_lands_in_the_package() -> None:
    assert "Native package must not ship WebEngine" in WORKFLOW
    assert WORKFLOW.count("Native package must not ship WebEngine") == 2
    assert "WebEngine core DLL missing" not in WORKFLOW
