"""The app icon: the dumbbell on a lime square, with every size Windows and Android ask for."""

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


LIME = (0xAD, 0xE6, 0x31)


def _image(path: Path):
    import pytest

    gui = pytest.importorskip("PySide6.QtGui")
    image = gui.QImage(str(path))
    assert not image.isNull(), path
    return image


def _rgba(image, x: int, y: int) -> tuple[int, int, int, int]:
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue(), color.alpha()


def _near(color: tuple[int, ...], want: tuple[int, ...]) -> bool:
    return all(abs(a - b) <= 3 for a, b in zip(color, want, strict=True))


def test_the_icon_is_the_dumbbell_on_a_lime_square_with_nothing_around_it() -> None:
    """Jonathan, 2026-11-24: the light grey square behind the logo showed as a white box on dark taskbars.
    The icon is now the dumbbell on a lime rounded square, and its corners are see-through."""
    logo = _image(ROOT / "desktop/assets/logo.png")
    last = logo.width() - 1
    for x, y in ((0, 0), (last, 0), (0, last), (last, last)):
        assert _rgba(logo, x, y)[3] == 0, (x, y)
    # Partway in from each edge's middle, past the rounded corners and short of the dumbbell: lime.
    for x, y in ((8, 128), (last - 8, 128), (128, 8), (128, last - 8)):
        assert _near(_rgba(logo, x, y), (*LIME, 255)), (x, y, _rgba(logo, x, y))


def test_the_android_launcher_shows_the_logo_at_every_density() -> None:
    """With no android:icon the phone showed Android's stock robot for FlexWeek."""
    import struct

    manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'android:icon="@mipmap/ic_launcher"' in manifest
    res = ROOT / "android/app/src/main/res"
    for density, side in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        data = (res / f"mipmap-{density}/ic_launcher.png").read_bytes()
        assert data[16:24] == struct.pack(">II", side, side), density


def test_the_android_launcher_draws_the_icon_in_its_own_shape_without_a_white_plate() -> None:
    """Android 8 and later put a plain square icon on a white plate. The adaptive icon gives the
    launcher a lime layer and a see-through dumbbell layer (108 dp), and it cuts them to its own shape."""
    import re

    res = ROOT / "android/app/src/main/res"
    adaptive = (res / "mipmap-anydpi-v26/ic_launcher.xml").read_text(encoding="utf-8")
    assert '<background android:drawable="@color/ic_launcher_background" />' in adaptive
    assert '<foreground android:drawable="@mipmap/ic_launcher_foreground" />' in adaptive
    colors = (res / "values/ic_launcher_background.xml").read_text(encoding="utf-8")
    found = re.search(r'<color name="ic_launcher_background">#([0-9A-Fa-f]{6})</color>', colors)
    assert found is not None
    assert tuple(bytes.fromhex(found.group(1))) == LIME
    for density, side in {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}.items():
        layer = _image(res / f"mipmap-{density}/ic_launcher_foreground.png")
        assert (layer.width(), layer.height()) == (side, side), density
        # The dumbbell sits in the middle; the rest of the layer lets the lime show through.
        assert _rgba(layer, 0, 0)[3] == 0 and _rgba(layer, side // 6, side // 2)[3] == 0, density
        assert _rgba(layer, side // 2, side // 2)[3] == 255, density
