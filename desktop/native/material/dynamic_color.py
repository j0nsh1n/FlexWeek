"""A Material scheme from a seed, and the platform accent when the desktop supplies one."""

from __future__ import annotations

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtGui import QGuiApplication, QPalette


def scheme(seed: str, style: str, dark: bool, contrast: float) -> dict[str, str]:
    """The 30 theme roles for one seed, palette style, mode and contrast."""
    return flexweek_engine.material_scheme(seed, style, dark, contrast)


def system_accent() -> str | None:
    """Qt's palette accent, as ``#rrggbb``, when the platform has set one.

    An offscreen palette still resolves a colour. That colour is not the
    platform's, so callers hide Dynamic color.
    """
    app = QGuiApplication.instance()
    if app is None:
        return None
    palette = app.palette()
    role = QPalette.ColorRole.Accent
    if not palette.isBrushSet(QPalette.ColorGroup.Active, role):
        return None
    colour = palette.color(role)
    if not colour.isValid():
        return None
    return f"#{colour.red():02x}{colour.green():02x}{colour.blue():02x}"
