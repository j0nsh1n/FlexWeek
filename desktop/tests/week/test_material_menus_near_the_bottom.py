"""The first block menu, and the first free-time menu, opened near the bottom of the Material window sit
whole inside it: the menu is placed after its rows are filled in, not while it still has none.

Each test opens its menu on a fresh window, because only the first one was ever misplaced (a later
open reused the height the last one left). Expected values come from the window: the menu's top and
bottom lie within the Quick widget that is the window's content.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import named, pump, qml  # noqa: E402
from desktop.tests.sheets.support_material_sheets import block_named, material_week  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

THURSDAY = 3


def scroll_to_the_end(qapp, root: QObject) -> None:
    scroller = qml(root, "weekScroller")
    scroller.setProperty(
        "contentY", float(scroller.property("contentHeight")) - float(scroller.property("height"))
    )
    pump(qapp)


def lies_inside_the_window(window: NativeWindow, menu: QObject) -> None:
    quick = window._material_page._quick
    top = menu.mapToScene(QPointF(0, 0)).y()
    assert top >= 0
    assert top + float(menu.property("height")) <= quick.height()


def test_the_first_block_menu_opened_near_the_bottom_is_inside_the_window(qapp, window: NativeWindow) -> None:
    root = material_week(qapp, window)
    window.session.add_block(
        {
            "id": "late",
            "title": "Late club",
            "kind": "locked",
            "category": "extra",
            "start": "23:00",
            "duration_min": 60,
            "days": [THURSDAY],
        }
    )
    window.session.save()
    settled(qapp, window)
    pump(qapp)
    scroll_to_the_end(qapp, root)
    block = block_named(root, "Late club")
    low = block.mapToScene(QPointF(block.width() / 2, block.height() * 0.9))
    QTest.mouseClick(
        window._material_page._quick, Qt.MouseButton.RightButton, pos=QPoint(int(low.x()), int(low.y()))
    )
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    lies_inside_the_window(window, menu)


def test_the_first_free_time_menu_opened_near_the_bottom_is_inside_the_window(
    qapp, window: NativeWindow
) -> None:
    root = material_week(qapp, window)
    scroll_to_the_end(qapp, root)
    scroller = qml(root, "weekScroller")
    # The last quarter hour of Saturday, a day with nothing on it.
    spot = scroller.mapToScene(QPointF(scroller.width() * 0.85, scroller.height() - 4))
    QTest.mouseClick(
        window._material_page._quick, Qt.MouseButton.LeftButton, pos=QPoint(int(spot.x()), int(spot.y()))
    )
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    lies_inside_the_window(window, menu)


def test_the_free_time_menu_with_paste_here_opened_by_right_click_near_the_bottom_is_inside_the_window(
    qapp, window: NativeWindow
) -> None:
    """The extra row makes the menu taller: it is still placed whole inside the window."""
    root = material_week(qapp, window)
    window.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "17:30",
            "duration_min": 60,
            "days": [THURSDAY],
        }
    )
    window.session.save()
    settled(qapp, window)
    assert window.session.copy_block("club", THURSDAY), "something is copied"
    scroll_to_the_end(qapp, root)
    scroller = qml(root, "weekScroller")
    spot = scroller.mapToScene(QPointF(scroller.width() * 0.85, scroller.height() - 4))
    QTest.mouseClick(
        window._material_page._quick, Qt.MouseButton.RightButton, pos=QPoint(int(spot.x()), int(spot.y()))
    )
    pump(qapp)
    menu = named(root, "blockMenu")[0]
    assert menu.property("open") is True
    assert [entry["label"] for entry in menu.property("entries").toVariant()][-1] == "Paste here"
    lies_inside_the_window(window, menu)
