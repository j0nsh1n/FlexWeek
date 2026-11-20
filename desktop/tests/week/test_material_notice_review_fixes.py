"""Review fixes for the Material snackbar: the Ctrl+Z hint is readable, and every Undo bar has its line."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.material.theme import DEFAULT_CONTRAST, DEFAULT_PRESET, scheme
from desktop.tests.week.support_material import (
    _bridge,
    _named,
    _pump,
    _qml,
    _reset,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp  # noqa: F401


def _rgb(colour: str) -> tuple[float, float, float]:
    text = colour.lstrip("#")[-6:]
    return tuple(int(text[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(rgb: tuple[float, float, float]) -> float:
    def lin(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (lin(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _ratio(ink: tuple[float, float, float], paper: tuple[float, float, float]) -> float:
    lighter, darker = sorted((_luminance(ink), _luminance(paper)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_ctrl_z_hint_reads_at_4_5_to_1_on_the_snackbar(qapp, window, mode: str) -> None:
    """The hint was drawn at 85 percent opacity: 3.70:1 in dark. It is drawn in the Undo text's colour."""
    root = _reset(window, qapp)
    _bridge(window).note("Placed 1 of 1")
    _pump(qapp, 20)
    (hint,) = _named(_qml(root, "materialSnackbar"), "shortcutHint")
    assert float(hint.property("opacity")) == 1.0
    colours = scheme(DEFAULT_PRESET, mode, DEFAULT_CONTRAST)
    ink, paper = _rgb(colours["inversePrimary"]), _rgb(colours["inverseSurface"])
    assert _ratio(ink, paper) >= 4.5, (mode, _ratio(ink, paper))


def test_every_undo_bar_has_its_line_when_animations_run(qapp, window) -> None:
    """A notice from the window's own `_set_notice` (a move, a plan) draws the same line as `note`."""
    root = _reset(window, qapp)
    bridge = _bridge(window)
    bridge._advanced = {**bridge._advanced, "motion": "Normal"}
    window.session.preferences = {**(window.session.preferences or {}), "motion": "normal"}
    bridge._publish_theme()
    window._set_notice("Moved School to Thu 8:00 AM.", "Undo", lambda: None)
    _pump(qapp, 20)
    (line,) = _named(_qml(root, "materialSnackbar"), "timeLine")
    assert line.property("visible") is True
    assert 0.9 < float(bridge.property("snackFraction")) <= 1.0
    assert float(line.property("width")) > 0
