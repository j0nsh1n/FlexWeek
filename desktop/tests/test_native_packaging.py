"""Packaged builds compile the native window and must not follow Chromium."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


def test_release_jobs_fail_if_chromium_lands_in_the_package() -> None:
    assert "Native package must not ship WebEngine" in WORKFLOW
    assert WORKFLOW.count("Native package must not ship WebEngine") == 2
    assert "WebEngine core DLL missing" not in WORKFLOW


def test_both_builds_ship_the_plugin_that_makes_an_alarm_audible() -> None:
    """QtMultimedia reaches the sound card through a Qt plugin. Trim it and the app still starts, the
    alarm still shows its dialog, and it rings silently, which is the one thing an alarm must not do."""
    for text in (LINUX, WINDOWS):
        assert "include-qt-plugins=multimedia," in text


def test_the_windows_build_takes_its_icon_from_the_ico_with_every_size() -> None:
    """Nuitka's --windows-icon-from-ico was handed the PNG. The .ico carries each size Windows asks
    for, made from the logo by scripts/brand.py."""
    import struct

    assert "--windows-icon-from-ico=$(Join-Path $Root 'desktop\\assets\\logo.ico')" in WINDOWS
    data = (ROOT / "desktop/assets/logo.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)
    sides = [data[6 + 16 * index] or 256 for index in range(count)]
    assert sides == [256, 128, 64, 48, 32, 16]
    assert (ROOT / "desktop/assets/logo.png").read_bytes()[16:24] == struct.pack(">II", 256, 256)


def test_the_icon_is_the_original_logo() -> None:
    """1.0.0 brings back the original logo, the green dumbbell on a phone, in place of the blue square
    0.16 drew. These are the bytes of the logo.png first committed on 2026-09-06."""
    import hashlib

    logo = (ROOT / "desktop/assets/logo.png").read_bytes()
    original = "59e1053076bb6e4e090e5a9333bc285312fd5f2e269d4d6c7f04c406a191f21d"
    assert hashlib.sha256(logo).hexdigest() == original


def test_the_android_launcher_shows_the_logo_at_every_density() -> None:
    """With no android:icon the phone showed Android's stock robot for FlexWeek."""
    import struct

    manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'android:icon="@mipmap/ic_launcher"' in manifest
    res = ROOT / "android/app/src/main/res"
    for density, side in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        data = (res / f"mipmap-{density}/ic_launcher.png").read_bytes()
        assert data[16:24] == struct.pack(">II", side, side), density


def test_both_builds_ship_the_icon_and_the_fonts_where_the_app_looks_for_them() -> None:
    """Nuitka compiles code and leaves every other file behind unless told. The icon never shipped
    before 0.16 for that reason, and the bundled Inter would not have either."""
    assert '--include-data-dir="$ROOT/desktop/assets=desktop/assets"' in LINUX
    assert "--include-data-dir=$(Join-Path $Root 'desktop\\assets')=desktop/assets" in WINDOWS
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
