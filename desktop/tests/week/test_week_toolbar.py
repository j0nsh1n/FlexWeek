# ruff: noqa: F811
"""The week page's top bar: which buttons it keeps in every design, that none is offered twice, and what
the Add button says about a drag."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_no_button_appears_twice_on_the_week_page(qapp: QApplication, window: NativeWindow) -> None:
    """Moving Quick focus into the action row left the focus panel's own copy on screen, so the same
    button was offered twice. The action row is not the only place a button can come from, so this counts
    them across the whole page rather than inside one container."""
    window._on_week()
    qapp.processEvents()
    page = window._stack.currentWidget()
    labels = [b.text() for b in page.findChildren(QPushButton) if b.isVisible() and b.text()]
    repeated = sorted({text for text in labels if labels.count(text) > 1})
    assert repeated == [], f"offered twice: {repeated}"


