"""What a packaged build contains: the native window without Chromium, the plugin that makes an alarm
audible, and the icon, fonts and sounds where the app looks for them."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LINUX = (ROOT / "desktop/build_linux.sh").read_text(encoding="utf-8")
WINDOWS = (ROOT / "desktop/build_windows.ps1").read_text(encoding="utf-8")
FINISH = (ROOT / "desktop/finish_linux_bundle.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/release-windows.yml").read_text(encoding="utf-8")

GONE = (
    "desktop/webengine.py",
    "desktop/sandbox.py",
    "desktop/tests/webengine_probe.py",
    "desktop/tests/test_webengine.py",
    "desktop/tests/test_sandbox.py",
)


def test_retired_chromium_shell_is_gone() -> None:
    for relative in GONE:
        assert not (ROOT / relative).exists(), relative


def test_nuitka_does_not_compile_chromium() -> None:
    assert "--include-package=desktop \\" not in LINUX
    assert "'--include-package=desktop'" not in WINDOWS
    for text in (LINUX, WINDOWS):
        assert "include-package=desktop.native" in text
        assert "include-module=flexweek_engine" in text
        assert "desktop.webengine" not in text
        assert "PySide6.QtWebEngineCore" in text
        assert "noinclude-module" not in text


def test_linux_trim_survives_a_bundle_with_no_chromium_locales() -> None:
    assert '[[ -d "$BUNDLE/qtwebengine_locales" ]]' in FINISH


def test_linux_bundle_drops_the_wayland_compositor_modules() -> None:
    # The bundle check rejects them: they need libwayland-server, which desktops need not have.
    trim = FINISH.index('rm -rf "$BUNDLE/PySide6/qml/QtWayland/Compositor"')
    assert FINISH.index('rm -f "$BUNDLE"/libQt6WaylandCompositor*.so*') > 0
    assert trim < FINISH.index("desktop.check_bundle"), "trim before the bundle check"


def test_release_jobs_fail_if_chromium_lands_in_the_package() -> None:
    assert "Native package must not ship WebEngine" in WORKFLOW
    assert WORKFLOW.count("Native package must not ship WebEngine") == 2
    assert "WebEngine core DLL missing" not in WORKFLOW


def test_both_builds_ship_the_plugin_that_makes_an_alarm_audible() -> None:
    """QtMultimedia reaches the sound card through a Qt plugin. Trim it and the app still starts, the
    alarm still shows its dialog, and it rings silently, which is the one thing an alarm must not do."""
    for text in (LINUX, WINDOWS):
        assert "include-qt-plugins=multimedia," in text


def test_both_builds_ship_the_icon_and_the_fonts_where_the_app_looks_for_them() -> None:
    """Nuitka compiles code and leaves every other file behind unless told. The icon never shipped
    before 0.16 for that reason, and the bundled Inter would not have either."""
    assert '--include-data-dir="$ROOT/desktop/assets=desktop/assets"' in LINUX
    assert "--include-data-dir=$(Join-Path $Root 'desktop\\assets')=desktop/assets" in WINDOWS
    assert (
        '--include-data-files="$ROOT/desktop/native/material/tokens.json=desktop/native/material/tokens.json"'
        in LINUX
    )
    assert '--include-data-dir="$ROOT/desktop/native/material/qml=desktop/native/material/qml"' in LINUX
    assert (
        "--include-data-files=$(Join-Path $Root 'desktop\\native\\material\\tokens.json')"
        "=desktop/native/material/tokens.json" in WINDOWS
    )
    assert (
        "--include-data-dir=$(Join-Path $Root 'desktop\\native\\material\\qml')=desktop/native/material/qml"
        in WINDOWS
    )
    sounds = ROOT / "desktop/assets/sounds"
    assert (sounds / "LICENSE.txt").is_file()
    assert (sounds / "soft-rain-loop.mp3").is_file()
    assert (sounds / "lofi-hip-hop-loop.ogg").is_file()
    fonts = ROOT / "desktop/assets/fonts"
    for family in ("Inter", "Newsreader", "JetBrainsMono", "PixelifySans"):
        for face in ("Regular", "Medium", "SemiBold", "Bold"):
            assert (fonts / f"{family}-{face}.ttf").is_file(), (family, face)
    assert (fonts / "VT323-Regular.ttf").is_file()
    for licence in (
        "LICENSE.txt",
        "Newsreader-OFL.txt",
        "JetBrainsMono-OFL.txt",
        "PixelifySans-OFL.txt",
        "VT323-OFL.txt",
    ):
        assert "SIL Open Font License" in (fonts / licence).read_text(encoding="utf-8"), licence


def test_linux_bundle_drops_qts_web_modules_before_the_check() -> None:
    # The packaged smoke refuses WebEngine; the QML copy would otherwise ship QtWebEngine and QtWebView.
    trim = FINISH.index("-iname '*webengine*' -o -iname '*webview*'")
    assert trim < FINISH.index("desktop.check_bundle"), "trim before the bundle check"


def test_windows_bundle_drops_qts_web_modules_before_the_check() -> None:
    # Same QML copy as on Linux: without the trim the Windows package ships QtWebEngine, which the smoke
    # refuses.
    trim = WINDOWS.index("-match 'webengine|webview'")
    assert trim < WINDOWS.index("desktop.check_bundle"), "trim before the bundle check"
