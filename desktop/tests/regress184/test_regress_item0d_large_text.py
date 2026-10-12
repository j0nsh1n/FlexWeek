"""Regression for fix-specs.md item 0d: passing through High contrast silently turns Large text off.

`settings.py::_built_in_look` keeps only knobs that differ from the worn preset (`look.py::look_overrides`);
High contrast's own `text` is "large", so while it is worn the student's Large is not kept and the next
look falls back to Normal. Driven through the Settings page of a signed-in window; "restart" is a new
NativeWindow on the same device, which reads the saved look file as the app does at start.
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton

from desktop.native.look import effective_look
from desktop.native.window import NativeWindow
from desktop.tests.window_support import free, qapp, server, settled, signed_out, window  # noqa: F401

KNOWN = "known failure (item 0d): Large is dropped while High contrast is worn; the next look is Normal"
KNOWN_KNOB = "known failure (item 0d): a knob moved by hand is forgotten when it equals the worn preset's"
KNOWN_SUGGEST = "known failure (item 0d): High contrast forces Large instead of suggesting it with Use"
TOKENS = {
    "Light": "pack:light-frost",
    "Dark": "pack:dark-frost",
    "High contrast": "preset:high-contrast",
    "Nocturne": "pack:nocturne",
    "Terminal": "preset:terminal",
}


def settings(qapp, window):
    window._open_settings()
    for _ in range(5):
        qapp.processEvents()
    return window._settings


def choose(qapp, page, knob: str, value: str) -> None:
    box = page.knobs[knob]
    box.setCurrentIndex(box.findData(value))
    qapp.processEvents()


def wear(qapp, page, look: str) -> None:
    page.look.setCurrentIndex(page.look.findData(TOKENS[look]))
    qapp.processEvents()


def shown(page, knob: str) -> str:
    return effective_look(page.look_choice())[knob]


def after_restart(qapp, server, knob: str) -> str:
    again = NativeWindow(server.origin)
    try:
        return effective_look(again._look)[knob]
    finally:
        again.hide()
        free(again)


def walk(qapp, page, looks: list[str], knob: str) -> list[tuple[str, str]]:
    seen = []
    for look in looks:
        wear(qapp, page, look)
        seen.append((look, shown(page, knob)))
    return seen


@pytest.mark.xfail(strict=True, reason=KNOWN)
def test_large_text_survives_light_dark_high_contrast_nocturne_light_and_a_restart(
    qapp, server, window
) -> None:
    """The spec's guard."""
    page = settings(qapp, window)
    choose(qapp, page, "text", "large")
    looks = ["Light", "Dark", "High contrast", "Nocturne", "Light"]
    seen = walk(qapp, page, looks, "text")
    window._close_settings(save=True)
    settled(qapp, window)
    seen.append(("after restart", after_restart(qapp, server, "text")))
    assert seen == [(look, "large") for look in looks] + [("after restart", "large")]


def test_large_text_survives_terminal_and_back_and_a_restart(qapp, server, window) -> None:
    """Guard (Assistant Local's run): a look whose own text size is Normal keeps the student's Large."""
    page = settings(qapp, window)
    choose(qapp, page, "text", "large")
    seen = walk(qapp, page, ["Terminal", "Light", "Nocturne"], "text")
    window._close_settings(save=True)
    settled(qapp, window)
    seen.append(("after restart", after_restart(qapp, server, "text")))
    assert [size for _look, size in seen] == ["large"] * 4, seen


@pytest.mark.xfail(strict=True, reason=KNOWN_KNOB)
def test_sharp_corners_moved_by_hand_survive_high_contrast(qapp, window) -> None:
    page = settings(qapp, window)
    choose(qapp, page, "corners", "sharp")
    seen = walk(qapp, page, ["High contrast", "Nocturne"], "corners")
    assert seen == [("High contrast", "sharp"), ("Nocturne", "sharp")]


@pytest.mark.xfail(strict=True, reason=KNOWN_SUGGEST)
def test_high_contrast_suggests_large_text_instead_of_forcing_it(qapp, window) -> None:
    page = settings(qapp, window)
    assert shown(page, "text") == "normal"
    wear(qapp, page, "High contrast")
    assert shown(page, "text") == "normal", "High contrast switched text size by itself"
    chip = [
        label for label in page.findChildren(QLabel) if label.isVisible() and "Suggests Large" in label.text()
    ]
    use = [b for b in page.findChildren(QPushButton) if b.isVisible() and b.text().replace("&", "") == "Use"]
    assert chip and use
