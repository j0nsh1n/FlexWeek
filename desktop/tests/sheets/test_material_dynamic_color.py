# ruff: noqa: F811
"""The Material scheme binding and the platform accent.

Expected colours are the reference schemes in ``tokens.json``. They are not
read back from a second call of the function under test.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from desktop.native.material.dynamic_color import scheme, system_accent

TOKENS = Path(__file__).resolve().parents[2] / "native" / "material" / "tokens.json"

PRESETS = (
    ("Slate", "#3D6FC4", "Tonal Spot"),
    ("Blue", "#0B62C4", "Tonal Spot"),
    ("Sea", "#00797F", "Tonal Spot"),
    ("Forest", "#3B7A4B", "Fidelity"),
    ("Gold", "#8A6A00", "Tonal Spot"),
    ("Rose", "#B4235A", "Vibrant"),
    ("Plum", "#6D4BC3", "Expressive"),
)


def _app() -> QApplication:
    found = QApplication.instance()
    if isinstance(found, QApplication):
        return found
    return QApplication([])


def test_the_binding_returns_every_reference_scheme() -> None:
    tokens = json.loads(TOKENS.read_text())
    for name, seed, style in PRESETS:
        for dark, mode in ((False, "light"), (True, "dark")):
            for contrast, level in ((0.0, "std"), (1.0, "high")):
                key = f"{name}.{mode}.{level}"
                assert scheme(seed, style, dark, contrast) == tokens[key]


def test_a_bad_seed_is_refused() -> None:
    with pytest.raises(ValueError, match="seed colour must be a hex colour"):
        scheme("not-a-colour", "Tonal Spot", False, 0)


def test_an_unknown_style_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown palette style"):
        scheme("#0B62C4", "Content", False, 0)


def test_contrast_outside_the_scale_is_refused() -> None:
    with pytest.raises(ValueError, match="contrast must be from -1 to 1"):
        scheme("#0B62C4", "Tonal Spot", False, 1.5)
    with pytest.raises(ValueError, match="contrast must be from -1 to 1"):
        scheme("#0B62C4", "Tonal Spot", False, math.nan)


def test_the_system_accent_is_the_platform_colour_when_it_has_one() -> None:
    app = _app()
    previous = app.palette()
    palette = QPalette(previous)
    palette.setColor(QPalette.ColorRole.Accent, QColor("#C2185B"))
    app.setPalette(palette)
    try:
        assert system_accent() == "#c2185b"
    finally:
        app.setPalette(previous)


def test_the_system_accent_is_absent_when_the_platform_has_none() -> None:
    app = _app()
    previous = app.palette()
    try:
        unset = QPalette()
        app.setPalette(unset)
        assert not unset.isBrushSet(QPalette.ColorGroup.Active, QPalette.ColorRole.Accent)
        assert system_accent() is None
        invalid = QPalette()
        invalid.setColor(QPalette.ColorRole.Accent, QColor())
        app.setPalette(invalid)
        assert system_accent() is None
    finally:
        app.setPalette(previous)
