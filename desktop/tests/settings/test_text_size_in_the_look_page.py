"""Text size sits on Settings' Look page on a fresh account, without turning on "Show shape, spacing and
type", and is listed once when that switch is on."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel

from desktop.native.settings import KNOB_LABELS, SECTIONS
from desktop.native.widgets import Segmented
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def look_page(qapp, window):
    window.resize(1280, 800)
    window._open_settings()
    page = window._settings
    page.nav.setCurrentRow(SECTIONS.index("Look"))
    for _ in range(5):
        qapp.processEvents()
    return page


def test_text_size_is_shown_on_a_fresh_account_without_any_switch(qapp, window) -> None:
    page = look_page(qapp, window)
    assert not page.fine_tune.isChecked()
    text = page.findChild(Segmented, "lookText")
    assert text is not None and text.isVisible()


def test_choosing_large_leaves_the_switch_off(qapp, window) -> None:
    page = look_page(qapp, window)
    text = page.findChild(Segmented, "lookText")
    assert text.isVisible(), "Text size not reachable without the switch"
    text.setCurrentIndex(text.findData("large"))
    qapp.processEvents()
    assert not page.fine_tune.isChecked()


def test_text_size_is_listed_once_with_the_switch_on(qapp, window) -> None:
    page = look_page(qapp, window)
    page.fine_tune.setChecked(True)
    qapp.processEvents()
    rows = [
        label
        for label in page.findChildren(QLabel)
        if label.isVisible() and label.text() == KNOB_LABELS["text"]
    ]
    assert len(rows) == 1
