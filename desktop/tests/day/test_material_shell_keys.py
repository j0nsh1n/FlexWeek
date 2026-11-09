# ruff: noqa: F811
"""Keys and focus in the Material shell: the number keys open the screens, Esc hands focus back to the
destination, Ctrl+S saves, and a focus ring shows only after a key, never after the mouse.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import material_window, qapp  # noqa: E402, F401
from desktop.tests.material_support import named, pump, qml, show_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


def _press_item(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(
        window._material_page._quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    pump(qapp)


def test_number_keys_open_each_screen_and_escape_returns_focus(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    """1-5 leave the week for Day, Month, My day, and Settings, and Esc focuses that destination."""
    root = show_material(qapp, material_window)
    bridge = material_window._material_page.bridge
    quick = material_window._material_page._quick
    assert bridge.property("screen") == "week"
    root.forceActiveFocus()
    pump(qapp)
    for key, screen, page_name, title in (
        (Qt.Key.Key_1, "day", "materialDay", "Day"),
        (Qt.Key.Key_3, "month", "materialMonth", "Month"),
        (Qt.Key.Key_4, "myday", "materialMyDay", "My day"),
        (Qt.Key.Key_5, "settings", "materialSettings", "Settings"),
        (Qt.Key.Key_2, "week", "materialWeek", None),
    ):
        QTest.keyClick(quick, key)
        pump(qapp)
        assert bridge.property("screen") == screen
        page = qml(root, page_name)
        assert page.property("visible") is True
        if title is not None:
            assert named(page, "screenTitle")[0].property("text") == title
    assert qml(root, "materialSettings").property("visible") is False

    bridge.showPage("settings")
    pump(qapp)
    settings = qml(root, "materialSettings")
    assert settings.property("visible") is True
    assert named(settings, "useWidgets")[0].property("text") == "Widgets styles"
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert qml(root, "navSettings").property("activeFocus") is True
    bridge.showPage("nope")
    assert bridge.property("screen") == "settings"
    bridge.showPage("week")
    pump(qapp)
    assert bridge.property("screen") == "week"
    assert named(root, "weekBlock")


def test_ctrl_s_saves_when_the_material_shell_is_focused(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    show_material(qapp, material_window)
    heard: list[bool] = []
    monkeypatch.setattr(material_window.session, "save", lambda: heard.append(True))
    material_window.session.dirty = True
    quick = material_window._material_page._quick
    quick.setFocus()
    pump(qapp)

    QTest.keyClick(quick, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)

    assert heard == [True]


def test_rings_follow_the_last_input_in_the_real_window(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    """A sheet opened with the mouse puts focus on Title, which has no ring. Esc is a key, so the focus it
    hands back shows its ring, even on the rail item that was just clicked."""
    root = show_material(qapp, material_window)
    sheets = material_window._material_page.bridge.sheets
    _press_item(qapp, material_window, named(root, "materialFab")[0])

    # Title marks focus with its own border (Material 3), so it has no ring to show.
    def focused() -> list[QObject]:
        return [
            field
            for title in named(root, "homeworkTitle")
            for field in named(title, "fieldInput")
            if field.property("activeFocus")
        ]

    wait_until(qapp, lambda: bool(focused()))
    assert not [ring for title in named(root, "homeworkTitle") for ring in named(title, "focusRing")]

    week = named(root, "navWeek")[0]
    sheets.forceClose()
    pump(qapp)
    _press_item(qapp, material_window, week)
    QTest.keyClick(material_window._material_page._quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert week.property("activeFocus") is True
    assert named(week, "focusRing")[0].property("shown") is True
