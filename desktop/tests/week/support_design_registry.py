"""Colour distance for the design registry tests."""

from __future__ import annotations


def _lab(colour: str) -> tuple[float, float, float]:
    """sRGB to CIE Lab, as the retired web client's theme-tokens test computed it."""

    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    raw = colour.lstrip("#")
    red, green, blue = (channel(int(raw[index : index + 2], 16) / 255) for index in (0, 2, 4))
    x = (red * 0.4124 + green * 0.3576 + blue * 0.1805) / 0.95047
    y = red * 0.2126 + green * 0.7152 + blue * 0.0722
    z = (red * 0.0193 + green * 0.1192 + blue * 0.9505) / 1.08883
    fx, fy, fz = (t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116 for t in (x, y, z))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))
