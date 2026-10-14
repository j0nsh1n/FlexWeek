"""Make FlexWeek's icon files from its original logo, desktop/assets/logo.png (256 px, the green
dumbbell on a phone).

    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/brand.py

Writes desktop/assets/logo.ico (256, 128, 64, 48, 32 and 16 px) for the Windows build, and the Android
launcher icon at each density under android/app/src/main/res/mipmap-*/ic_launcher.png. Run it again
after logo.png changes. 1.0.0 brought the original logo back in place of the blue one 0.16 drew.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402

ASSETS = ROOT / "desktop" / "assets"
LOGO = ASSETS / "logo.png"
ICO_SIZES = (256, 128, 64, 48, 32, 16)
# Android's launcher icon at each screen density, 48 dp.
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"
LAUNCHER_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def scaled(logo: QImage, size: int) -> QImage:
    if logo.width() == size:
        return logo
    keep = Qt.AspectRatioMode.KeepAspectRatio
    return logo.scaled(size, size, keep, Qt.TransformationMode.SmoothTransformation)


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


def dib_bytes(image: QImage) -> bytes:
    """An icon entry as Windows reads one below 256 px: a bitmap header, the colours bottom row first,
    then a mask of zeros, since the colours carry their own transparency."""
    size = image.width()
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    rows = []
    for y in reversed(range(size)):
        row = bytearray()
        for x in range(size):
            color = image.pixelColor(x, y)
            row += bytes((color.blue(), color.green(), color.red(), color.alpha()))
        rows.append(bytes(row))
    mask_row = b"\0" * (((size + 31) // 32) * 4)
    return header + b"".join(rows) + mask_row * size


def ico_bytes(images: list[QImage]) -> bytes:
    entries = [png_bytes(image) if image.width() >= 256 else dib_bytes(image) for image in images]
    offset = 6 + 16 * len(images)
    directory = struct.pack("<HHH", 0, 1, len(images))
    for image, data in zip(images, entries, strict=True):
        side = image.width() % 256
        directory += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return directory + b"".join(entries)


def main() -> int:
    application = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    logo = QImage(str(LOGO)).convertToFormat(QImage.Format.Format_ARGB32)
    if logo.isNull():
        print(f"Could not read {LOGO}", file=sys.stderr)
        return 1
    (ASSETS / "logo.ico").write_bytes(ico_bytes([scaled(logo, size) for size in ICO_SIZES]))
    for density, size in LAUNCHER_SIZES.items():
        folder = ANDROID_RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        if not scaled(logo, size).save(str(folder / "ic_launcher.png"), "PNG"):
            print(f"Could not write {folder / 'ic_launcher.png'}", file=sys.stderr)
            return 1
    print(f"Wrote {ASSETS / 'logo.ico'} and the Android launcher icons from {LOGO}.")
    del application
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
