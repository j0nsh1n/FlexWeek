# ruff: noqa: F811
"""The Material focus ring appears for the keyboard and not for the mouse: a press anywhere hides it, even
on the control that keeps focus, a key brings it back, the first click into a field and focus given from
code after a click stay quiet, a selected rail item shows none until focused, and a text field marks focus
with its own border instead of a ring.

How the ring looks (width, radius, colour, the gap round the control) is judged on the pictures
(screens `week.material_add_button_and_rail` and `sheets.material_homework_sheet`).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from desktop.native.material.focus_visible import install  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    gallery,
    gallery_child,
    gallery_find,
    qapp,
)


def _click(view: QQuickView, item: QQuickItem) -> None:
    view.requestActivate()
    QGuiApplication.processEvents()
    centre = item.mapToItem(view.contentItem(), QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre.toPoint())
    QGuiApplication.processEvents()


def test_a_mouse_click_shows_no_ring_and_tab_does(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """A ring shows on the focused control only after a key; any mouse press hides it, the first click on
    a field included, and a key on the same control brings it back."""
    view, root = gallery
    assert install(view.engine()) is not None
    button = gallery_find(root, "filledMeasure")
    ring = gallery_child(button, "focusRing")
    field = gallery_find(root, "fieldMeasure")
    dest = gallery_find(root, "destMeasure")
    dest_ring = gallery_child(dest, "focusRing")

    view.requestActivate()
    QTest.keyClick(view, Qt.Key.Key_Tab)
    button.forceActiveFocus(Qt.FocusReason.TabFocusReason)
    QGuiApplication.processEvents()
    assert ring.property("shown") is True

    # A press anywhere hides the ring, even though the button keeps focus.
    _click(view, dest)
    assert button.hasActiveFocus()
    assert ring.property("shown") is False

    # A key on the same control brings it back.
    QTest.keyClick(view, Qt.Key.Key_Shift)
    QGuiApplication.processEvents()
    assert ring.property("shown") is True

    # A click into a field focuses it; the field marks focus with its own border, not a ring.
    _click(view, field)
    assert field.property("activeFocus") or any(
        child.hasActiveFocus() for child in field.findChildren(type(field))
    )

    # Focus given from code after a click (a mouse-opened sheet's first field) stays quiet too.
    dest.forceActiveFocus(Qt.FocusReason.OtherFocusReason)
    QGuiApplication.processEvents()
    assert dest.hasActiveFocus()
    assert dest_ring.property("shown") is False
    QTest.keyClick(view, Qt.Key.Key_Shift)
    QGuiApplication.processEvents()
    assert dest_ring.property("shown") is True


def test_the_selected_rail_item_is_selected_and_shows_no_ring_until_it_has_focus(
    gallery: tuple[QQuickView, QQuickItem],
) -> None:
    _view, root = gallery
    dest = gallery_find(root, "destMeasure")
    ring = gallery_child(dest, "focusRing")

    assert dest.property("selected") is True
    assert ring.property("shown") is False


def test_a_focused_field_draws_one_border(gallery: tuple[QQuickView, QQuickItem]) -> None:
    """Material 3 (Jonathan 2026-11-07): a field marks focus with its own border, so it has no outer
    ring to draw a second one. How that border looks is judged on the pictures."""
    _view, root = gallery
    field = gallery_find(root, "fieldMeasure")
    input_item = gallery_child(field, "fieldInput")

    assert not field.findChildren(QObject, "focusRing")

    field.forceActiveFocus(Qt.FocusReason.TabFocusReason)
    QGuiApplication.processEvents()

    assert input_item.hasActiveFocus()
    assert not field.findChildren(QObject, "focusRing")
