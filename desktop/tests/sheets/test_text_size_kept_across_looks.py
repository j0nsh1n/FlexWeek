"""Material's text size setting applies at once and stays when the preset changes or a saved look is applied.
How much larger the Week and Day rows are drawn is a picture (desktop/tests/pictures/_week_g14.py and
_day_g14.py, material_larger_text_rows)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.material.theme import SCALE_RANGE
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump
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
