# ruff: noqa: F811
"""The Get developer builds switch in Settings, This computer: both designs show the one saved setting,
and a developer build says so beside its version."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from desktop.native import window as window_module
from desktop.native.material import bridge_settings
from desktop.native.version import VERSION
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import faded_in
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def visuals(item: QObject) -> list[QObject]:
    """Every painted QML child (findChildren misses a repeater's rows: their QObject parent is the
    repeater model, their visual parent is the grid)."""
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(visuals(child))
    return found


def named(root: QObject, name: str) -> list[QObject]:
    return [item for item in visuals(root) if str(item.objectName()) == name]


def texts(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems():
        if child.property("text") is not None and child.property("font") is not None:
            found.append(child)
        found.extend(texts(child))
    return found


def panel(window: NativeWindow):
    return window._material_page.bridge._settings_bridge


def show_material(qapp: QApplication, window: NativeWindow) -> QObject:
    window._surface = "material"
    window._material_gave_up = False
    window._material_failed = ""
    window.resize(1280, 800)
    window._on_week()
    pump(qapp)
    window._material_page._quick.grabFramebuffer()
    pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    root = window._material_page.root
    assert root is not None
    faded_in(qapp, root)
    return root


def open_computer_section(qapp: QApplication, window: NativeWindow) -> QObject:
    root = show_material(qapp, window)
    window._material_page.bridge.showPage("settings")
    panel(window).closeAdvanced()
    panel(window).setSection("computer")
    pump(qapp)
    return root


def flick_to(item: QObject) -> None:
    """Scroll the nearest Flickable above `item` so the item is on screen."""
    parent = item.parentItem()
    while parent is not None:
        if parent.property("contentY") is not None and parent.property("contentHeight") is not None:
            content = parent.property("contentItem")
            spot = item.mapToItem(content, QPointF(0, 0))
            room = max(0.0, float(parent.property("contentHeight")) - float(parent.height()))
            parent.setProperty("contentY", max(0.0, min(room, spot.y() - 60.0)))
            return
        parent = parent.parentItem()


def click(qapp: QApplication, window: NativeWindow, item: QObject) -> None:
    pump(qapp, 5)
    flick_to(item)
    pump(qapp, 5)
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(
        window._material_page._quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(centre.x()), int(centre.y())),
    )
    pump(qapp, 10)


def test_material_switch_saves_the_setting(qapp: QApplication, window: NativeWindow) -> None:
    root = open_computer_section(qapp, window)
    row = named(root, "developerBuildsRow")[0]
    switch = next(item for item in visuals(row) if str(item.objectName()) == "developerBuilds")
    click(qapp, window, switch)
    wait_until(qapp, lambda: window._updates.get("developer_builds") is True)
    saved = json.loads(look_file().read_text(encoding="utf-8"))
    assert saved["updates"]["developer_builds"] is True


def test_a_developer_build_says_so_beside_its_version_in_material_settings(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = open_computer_section(qapp, window)
    settings = panel(window)
    assert settings.state["version"] == f"FlexWeek {VERSION}"
    assert "developer build" not in settings.state["version"]
    monkeypatch.setattr(bridge_settings, "CHANNEL", "dev")
    settings._publish()
    pump(qapp)
    assert settings.state["version"] == f"FlexWeek {VERSION} (developer build)"
    words = " ".join(str(item.property("text") or "") for item in texts(named(root, "row_updates")[0]))
    assert "developer build" in words


def test_widgets_settings_has_the_same_switch(qapp: QApplication, window: NativeWindow) -> None:
    """The switch was only in Material's Settings; Widgets This computer shows the same saved setting."""
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._updates["developer_builds"] = True
    window._save_look()
    assert json.loads(look_file().read_text(encoding="utf-8"))["updates"]["developer_builds"] is True
    window._open_settings()
    switch = window._settings.findChild(QWidget, "prefDeveloperBuilds")
    assert switch is not None and switch.isChecked() is True
    switch.click()
    qapp.processEvents()
    assert window._updates["developer_builds"] is False
    assert json.loads(look_file().read_text(encoding="utf-8"))["updates"]["developer_builds"] is False
    window._close_settings()
    window._updates["developer_builds"] = True  # as Material's switch would
    window._open_settings()
    assert window._settings.findChild(QWidget, "prefDeveloperBuilds").isChecked() is True


@pytest.mark.parametrize("kind", ["windows", "appimage"])
def test_widgets_settings_hides_the_switch_off_the_linux_tarball(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Developer builds are published for the Linux tarball only; elsewhere the switch would do nothing."""
    monkeypatch.setattr(window_module, "install_kind", lambda *_args, **_kw: kind)
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._open_settings()
    switch = window._settings.findChild(QWidget, "prefDeveloperBuilds")
    assert switch is not None and switch.isHidden() is True


def test_widgets_settings_shows_the_switch_on_the_linux_tarball(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window_module, "install_kind", lambda *_args, **_kw: "tarball")
    window._surface = "widgets"
    window._material_gave_up = False
    window._on_week()
    window._open_settings()
    switch = window._settings.findChild(QWidget, "prefDeveloperBuilds")
    assert switch is not None and switch.isHidden() is False


@pytest.mark.parametrize(("kind", "shown"), [("windows", False), ("appimage", False), ("tarball", True)])
def test_material_settings_shows_the_switch_only_on_the_linux_tarball(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch, kind: str, shown: bool
) -> None:
    monkeypatch.setattr(bridge_settings, "install_kind", lambda *_args, **_kw: kind)
    root = open_computer_section(qapp, window)
    row = named(root, "developerBuildsRow")[0]
    assert bool(row.property("visible")) is shown
    assert panel(window).state["developerBuildsOffered"] is shown
