"""The app icon: the original logo, with every size Windows and Android ask for."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WINDOWS = (ROOT / "desktop/build_windows.ps1").read_text(encoding="utf-8")


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
