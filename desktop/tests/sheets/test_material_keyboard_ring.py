# ruff: noqa: F811
"""The Material focus ring appears for the keyboard and not for the mouse: a press anywhere hides it, even
on the control that keeps focus, a key brings it back, the first click into a field and focus given from
code after a click stay quiet, a selected rail item shows none until focused, and a field that takes Tab
focus shows one.

How the ring looks (width, radius, colour, the gap round the control) is judged on the pictures
(screens `week.material_add_button_and_rail` and `sheets.material_homework_sheet`).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
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
    field_ring = gallery_child(field, "focusRing")
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

    # The first click into a field focuses it with no ring.
    _click(view, field)
    assert field.property("activeFocus") or any(
        child.hasActiveFocus() for child in field.findChildren(type(field))
    )
    assert field_ring.property("shown") is False

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


def test_a_field_given_focus_by_tab_shows_its_ring(gallery: tuple[QQuickView, QQuickItem]) -> None:
    _view, root = gallery
    field = gallery_find(root, "fieldMeasure")
    input_item = gallery_child(field, "fieldInput")
    ring = gallery_child(field, "focusRing")

    assert ring.property("shown") is False

    input_item.forceActiveFocus(Qt.FocusReason.TabFocusReason)
    QGuiApplication.processEvents()

    assert ring.property("shown") is True
