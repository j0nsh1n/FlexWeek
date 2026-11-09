# ruff: noqa: F811
"""What the shared Material 3 controls do from the keyboard, and what the mini month says.

How big and what colour each control is a picture (desktop/tests/pictures/_sheets_g11.py).
"""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtQuick import QQuickItem, QQuickView

    from desktop.tests.sheets.support_material_gallery import (  # noqa: F401
        _find,
        _press,
        gallery,
        qapp,
    )


def test_arrow_keys_move_the_segmented_button(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """Right arrow leaves Comfortable and selects Compact."""
    view, root = gallery
    segmented = _find(root, "segmentMeasure")
    assert segmented.property("current") == "comfortable"
    _press(view, segmented, Qt.Key.Key_Right)
    assert segmented.property("current") == "compact"


def test_space_turns_a_switch_on(gallery: tuple[QQuickView, QQuickItem]) -> None:
    view, root = gallery
    switch = _find(root, "switchMeasure")
    assert switch.property("checked") is False
    _press(view, switch, Qt.Key.Key_Space)
    assert switch.property("checked") is True


def test_mini_month_opens_on_monday_the_26th(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """November 2026 starts on Sunday, so the Monday-first grid opens on 26 and ends its first row on 1."""
    _view, root = gallery
    month = _find(root, "monthMeasure")
    assert _find(month, "cell0").property("text") == "26"
    assert _find(month, "cell6").property("text") == "1"


def test_mini_month_shows_the_keyboard_cursor(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """Tabbing onto the month shows a ring on the cursor, and arrows move it before Enter picks the day."""
    view, root = gallery
    month = _find(root, "monthMeasure")
    heard: list[int] = []
    month.dayActivated.connect(lambda day: heard.append(int(day)))
    with pytest.raises(AssertionError, match="cursorRing"):
        _find(month, "cursorRing")
    _press(view, month, Qt.Key.Key_Right)
    assert month.property("cursor") == 6
    ring = _find(month, "cursorRing")
    assert ring.isVisible() is True
    cell = _find(month, "cell10")
    iface = QAccessible.queryAccessibleInterface(cell)
    assert iface is not None
    assert iface.text(QAccessible.Text.Name) == "5"
    _press(view, month, Qt.Key.Key_Return)
    assert heard == [6]
