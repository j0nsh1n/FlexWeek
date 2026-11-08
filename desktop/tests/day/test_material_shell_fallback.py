# ruff: noqa: F811
"""When Material 3 cannot open, FlexWeek shows the Widgets week with a toast, keeps the student's week and
their choice, and does not try again until the version changes or they choose Material again.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from desktop.native.version import VERSION  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import (  # noqa: E402
    FALLBACK,
)
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.window_support import look_file  # noqa: E402


def _drop_material(window: NativeWindow, qapp: QApplication) -> None:
    """Remove the Material page, including one whose constructor died before it was stored."""
    doomed: list[QWidget] = []
    page = window._material_page
    window._material_page = None
    if page is not None:
        doomed.append(page)
    doomed.extend(window.findChildren(QWidget, "materialPage"))
    seen: set[int] = set()
    for item in doomed:
        if id(item) in seen:
            continue
        seen.add(id(item))
        if window._stack.indexOf(item) >= 0:
            window._stack.removeWidget(item)
        item.setParent(None)
        item.deleteLater()
    for bridge in window.findChildren(QObject, "materialBridge"):
        dispose = getattr(bridge, "dispose", None)
        if callable(dispose):
            dispose()
        bridge.setParent(None)
        bridge.deleteLater()
    pump(qapp)


def _blocks(window: NativeWindow) -> list[tuple[str, str]]:
    return [(block["id"], block["title"]) for block in window.session.blocks]


def test_a_load_or_graphics_failure_keeps_the_session_and_the_choice(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    window._surface = "material"
    window._material_gave_up = False
    window._save_look()
    before = _blocks(window)
    told = window.session.message
    page = window._ensure_material()
    assert page is not None
    page.break_load = True

    window._on_week()
    pump(qapp)

    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window.toast.isVisible()
    assert window.toast.text() == FALLBACK
    assert _blocks(window) == before
    assert json.loads(look_file().read_text())["surface"] == "material"
    assert window._surface == "material"
    assert window.session.message not in ("", told)
    window._on_week()
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert _blocks(window) == before

    window._material_gave_up = False
    page.break_load = False
    page._on_scene_graph_error(None, "device lost")
    pump(qapp)
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert _blocks(window) == before
    assert json.loads(look_file().read_text())["surface"] == "material"
    assert window._surface == "material"


def test_a_missing_or_broken_token_file_falls_back_and_leaves_no_material_page(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from desktop.native.material import theme

    window = material_window
    _drop_material(window, qapp)
    theme._schemes.cache_clear()
    missing = tmp_path / "tokens.json"
    monkeypatch.setattr(theme, "tokens_path", lambda: missing)
    window._surface = "material"
    window._material_gave_up = False
    window.toast.hide()
    try:
        window._on_week()
        pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window.toast.isVisible()
        assert window.toast.text() == FALLBACK
        assert window._surface == "material"
        assert window.findChild(QWidget, "materialPage") is None

        broken = tmp_path / "broken.json"
        broken.write_text("{", encoding="utf-8")
        monkeypatch.setattr(theme, "tokens_path", lambda: broken)
        theme._schemes.cache_clear()
        window._material_gave_up = False
        window._material_failed = ""
        window.toast.hide()
        window._on_week()
        pump(qapp)
        assert window._stack.currentWidget().objectName() == "weekPage"
        assert window.toast.text() == FALLBACK
        assert window.findChild(QWidget, "materialPage") is None
    finally:
        # The scheme cache is shared by the whole run, so it must not keep the broken file's answer.
        theme._schemes.cache_clear()
        _drop_material(window, qapp)


def test_a_publish_failure_falls_back_to_the_widgets_week(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    window._surface = "widgets"
    window._material_gave_up = False
    window._material_failed = ""
    page = window._ensure_material()
    assert page is not None

    def boom() -> None:
        raise RuntimeError("publication failed")

    page.publish = boom
    window._surface = "material"
    window.toast.hide()

    window._on_week()
    pump(qapp)

    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window.toast.isVisible()
    assert window.toast.text() == FALLBACK
    assert window._surface == "material"
    assert _blocks(window)


def test_a_failed_material_is_not_tried_again_until_the_version_or_a_new_choice(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    window.toast.hide()
    window._surface = "material"
    window._material_failed = VERSION
    window._material_gave_up = False
    window._save_look()
    window._material_gave_up = False
    window._load_look()
    window._on_week()
    pump(qapp)

    assert window._material_gave_up is True
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert window.toast.isHidden()
    assert json.loads(look_file().read_text())["surface"] == "material"

    # A different version tries again.
    stored = json.loads(look_file().read_text())
    stored["material_failed"] = "0.0.0"
    look_file().write_text(json.dumps(stored))
    window._load_look()
    assert window._material_gave_up is False
    window._on_week()
    pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    window._use_widgets_styles()
    pump(qapp)
    assert "material_failed" not in json.loads(look_file().read_text())

    # Choosing Material again in Settings tries again too.
    window._surface = "material"
    window._material_failed = VERSION
    window._material_gave_up = True
    window._save_look()
    window._open_settings()
    window._settings.findChild(QPushButton, "chooseMaterial").click()
    pump(qapp)
    assert window._stack.currentWidget().objectName() == "materialPage"
    assert "material_failed" not in json.loads(look_file().read_text())
