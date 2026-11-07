"""The text size and corners a student chose stay chosen when they wear another look (High contrast,
Nocturne, Terminal), close Settings and start the app again. High contrast suggests Large text and never
switches to it by itself."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton

from desktop.native.look import effective_look, sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.light_app import ORIGIN, window  # noqa: F401
from desktop.tests.window_support import free, qapp, settled  # noqa: F401

TOKENS = {
    "Light": "pack:light-frost",
    "Dark": "pack:dark-frost",
    "High contrast": "preset:high-contrast",
    "Nocturne": "pack:nocturne",
    "Terminal": "preset:terminal",
}
SUGGESTION = "High contrast is easiest to read with Large text."


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


def after_restart(knob: str) -> str:
    """A new window on this computer reads the saved look file, as the app does at start."""
    again = NativeWindow(ORIGIN)
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


def test_large_text_survives_light_dark_high_contrast_nocturne_light_and_a_restart(qapp, window) -> None:
    page = settings(qapp, window)
    choose(qapp, page, "text", "large")
    looks = ["Light", "Dark", "High contrast", "Nocturne", "Light"]
    seen = walk(qapp, page, looks, "text")
    window._close_settings(save=True)
    settled(qapp, window)
    seen.append(("after restart", after_restart("text")))
    assert seen == [(look, "large") for look in looks] + [("after restart", "large")]


def test_large_text_survives_terminal_and_back_and_a_restart(qapp, window) -> None:
    """A look whose own text size is Normal keeps the student's Large."""
    page = settings(qapp, window)
    choose(qapp, page, "text", "large")
    seen = walk(qapp, page, ["Terminal", "Light", "Nocturne"], "text")
    window._close_settings(save=True)
    settled(qapp, window)
    seen.append(("after restart", after_restart("text")))
    assert [size for _look, size in seen] == ["large"] * 4, seen


def test_sharp_corners_moved_by_hand_survive_high_contrast(qapp, window) -> None:
    page = settings(qapp, window)
    choose(qapp, page, "corners", "sharp")
    seen = walk(qapp, page, ["High contrast", "Nocturne"], "corners")
    assert seen == [("High contrast", "sharp"), ("Nocturne", "sharp")]


def test_high_contrast_suggests_large_text_instead_of_forcing_it(qapp, window) -> None:
    page = settings(qapp, window)
    assert shown(page, "text") == "normal"
    wear(qapp, page, "High contrast")
    assert shown(page, "text") == "normal", "High contrast switched text size by itself"
    chip = [label for label in page.findChildren(QLabel) if label.isVisible() and label.text() == SUGGESTION]
    use = [
        button
        for button in page.findChildren(QPushButton)
        if button.isVisible() and button.text().replace("&", "") == "Use Large text"
    ]
    assert chip and use


def test_an_account_saved_on_high_contrast_keeps_its_large_text_on_the_next_look(qapp, window) -> None:
    """A look saved before 0.19.0 wore High contrast with no text knob, so its Large came from the preset."""
    window._look = sanitize_look({"preset": "high-contrast", "knobs": {}})
    page = settings(qapp, window)
    assert shown(page, "text") == "large"
    assert walk(qapp, page, ["Nocturne", "Light"], "text") == [("Nocturne", "large"), ("Light", "large")]


def test_the_suggestion_goes_once_large_is_chosen_and_never_shows_on_other_looks(qapp, window) -> None:
    page = settings(qapp, window)
    wear(qapp, page, "Nocturne")
    assert not page.text_suggest.isVisibleTo(page)
    wear(qapp, page, "High contrast")
    assert page.text_suggest.isVisibleTo(page)
    use = next(b for b in page.findChildren(QPushButton) if b.text() == "Use Large text")
    use.click()
    qapp.processEvents()
    assert shown(page, "text") == "large"
    assert page.knobs["text"].currentData() == "large"
    assert not page.text_suggest.isVisibleTo(page)
