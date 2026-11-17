"""Material: an open drop-down list (Settings > Planning "Week starts on", and the lists in the sheets) moves
with Up and Down and picks with Enter, as the closed field does."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native import fields
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, visuals
from desktop.tests.settings.support_material_settings import _named, _open_settings
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def _key(window: NativeWindow, qapp: QApplication, key: Qt.Key) -> None:
    QTest.keyClick(window._material_page._quick, key)
    pump(qapp, 6)


def _open_lists(window: NativeWindow) -> list:
    scene = window._material_page._quick.quickWindow().contentItem()
    return [item for item in visuals(scene) if str(item.objectName()) == "pickerList"]


def test_the_open_week_start_list_moves_with_down_and_picks_with_enter(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    field = _named(root, "weekStart")[0]
    field.forceActiveFocus()
    pump(qapp)
    _key(window, qapp, Qt.Key.Key_Return)
    assert _open_lists(window), "the Week starts on list did not open"

    _key(window, qapp, Qt.Key.Key_Down)
    _key(window, qapp, Qt.Key.Key_Down)
    _key(window, qapp, Qt.Key.Key_Return)

    assert fields.week_starts_on() == "wednesday"
    assert not _open_lists(window) or not _open_lists(window)[0].property("visible")
