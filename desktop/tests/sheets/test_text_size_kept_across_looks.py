"""Material's text size setting applies at once, reaches every screen's words, and stays when the preset
changes or a saved look is applied. How much larger the Week and Day rows are drawn is a picture
(desktop/tests/pictures/_week_g14.py and _day_g14.py, material_larger_text_rows)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.material.theme import SCALE_RANGE
from desktop.native.window import NativeWindow
from desktop.tests.day.support_material_window import material_window  # noqa: F401
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump, qml, show_material
from desktop.tests.week.support_material_page import fresh_material


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-text-size-kept"])


def test_text_size_applies_live_and_the_week_hour_row_grows(qapp: QApplication, window: NativeWindow) -> None:
    fresh_material(qapp, window)
    bridge = window._material_page.bridge
    # The largest scale reaches at least 1.6 times.
    assert SCALE_RANGE[1] >= 1.6

    bridge.showPage("week")
    pump(qapp, 5)
    normal_hour_row = int(bridge.property("hourRow"))

    bridge.showPage("settings")
    pump(qapp, 5)
    settings_bridge = bridge._settings_bridge
    assert hasattr(settings_bridge, "setTextSize")
    settings_bridge.setTextSize("larger")
    pump(qapp, 15)
    assert settings_bridge.state["textSize"] == "larger"

    bridge.showPage("week")
    pump(qapp, 10)
    assert int(bridge.property("hourRow")) > normal_hour_row

    settings_bridge.setTextSize("normal")
    pump(qapp, 10)
    assert int(bridge.property("hourRow")) == normal_hour_row


def test_text_size_preserved_when_preset_changes_or_saved_look_applied(
    qapp: QApplication, window: NativeWindow
) -> None:
    fresh_material(qapp, window)
    bridge = window._material_page.bridge
    settings_bridge = bridge._settings_bridge
    bridge.showPage("week")
    pump(qapp, 5)
    normal_hour_row = int(bridge.property("hourRow"))

    bridge.showPage("settings")
    pump(qapp, 5)
    settings_bridge.setTextSize("larger")
    pump(qapp, 5)
    assert settings_bridge.state["textSize"] == "larger"

    # Change the preset and discard the advanced overrides
    other_preset = "Forest" if settings_bridge.state["preset"] != "Forest" else "Rose"
    settings_bridge.setPreset(other_preset)
    pump(qapp, 5)
    assert settings_bridge.property("promptOpen") is True
    settings_bridge.answerPreset("discard")
    pump(qapp, 10)

    # The text size is still larger, and so are the Week's hour rows
    assert settings_bridge.state["textSize"] == "larger"
    bridge.showPage("week")
    pump(qapp, 10)
    assert int(bridge.property("hourRow")) > normal_hour_row

    # A saved look made at normal size
    bridge.showPage("settings")
    pump(qapp, 5)
    settings_bridge.setTextSize("normal")
    pump(qapp, 5)
    settings_bridge.saveAs("NormalLook")
    pump(qapp, 5)

    settings_bridge.setTextSize("larger")
    pump(qapp, 5)
    assert settings_bridge.state["textSize"] == "larger"

    # Applying it keeps the student's text size
    settings_bridge.useSaved("NormalLook")
    pump(qapp, 10)
    assert settings_bridge.state["textSize"] == "larger"
    bridge.showPage("week")
    pump(qapp, 10)
    assert int(bridge.property("hourRow")) > normal_hour_row


QML_ROOT = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"
# The component gallery is a test page; the zoom pill's − and + sit in a fixed pill; the Focus
# clock already sizes from the window.
FIXED_SIZE_ALLOWED = {
    ("components/Gallery.qml", "24"),
    ("week/ZoomPill.qml", "14"),
    ("focus/FocusScreen.qml", "Math.round(88 * root.scale)"),
}


def test_every_material_text_size_goes_through_the_students_text_size() -> None:
    """V24: a fixed font.pixelSize never grows with Large text, so every one reads M3Font.px()."""
    fixed: list[str] = []
    for path in sorted(QML_ROOT.rglob("*.qml")):
        rel = path.relative_to(QML_ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "font.pixelSize:" not in line:
                continue
            value = line.split("font.pixelSize:", 1)[1].strip()
            if value.startswith("M3Font.px(") or (rel, value) in FIXED_SIZE_ALLOWED:
                continue
            fixed.append(f"{rel}:{number}: {value}")
    assert fixed == []


def _sizes_on_each_screen(qapp: QApplication, window: NativeWindow, root: QObject) -> dict[str, int]:
    bridge = window._material_page.bridge
    sizes: dict[str, int] = {}
    # A Settings row title sits inside the Settings screen; "title" alone names other things too.
    for screen, scope, name in (
        ("day", "", "dayNowTitle"),
        ("month", "", "monthDayNumber"),
        ("settings", "materialSettings", "title"),
    ):
        bridge.showPage(screen)
        pump(qapp, 40)
        found = named(qml(root, scope) if scope else root, name)
        assert found, name
        sizes[name] = found[0].property("font").pixelSize()
    bridge.showPage("week")
    window._open_focus_screen()
    pump(qapp, 40)
    sizes["focusTitle"] = qml(root, "focusTitle").property("font").pixelSize()
    bridge.focus.hide()
    pump(qapp)
    return sizes


def test_larger_text_reaches_day_month_settings_and_focus(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    root = show_material(qapp, window)
    bridge = window._material_page.bridge
    settings = bridge.settingsBridge
    try:
        before = _sizes_on_each_screen(qapp, window, root)
        settings.setTextSize("larger")
        pump(qapp)
        after = _sizes_on_each_screen(qapp, window, root)
        assert after == {name: round(size * 1.6) for name, size in before.items()}
    finally:
        settings.setTextSize("normal")
        bridge.showPage("week")
        pump(qapp)
