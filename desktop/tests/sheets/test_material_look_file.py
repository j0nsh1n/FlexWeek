# ruff: noqa: F811
"""The look file keeps the chosen surface (Widgets styles or Material 3) beside, not inside, the layout, and
an old or odd file opens on the Widgets styles.
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.custom_look import save_look, wear  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.look import sanitize_look  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import NIGHT, material_window, qapp  # noqa: E402, F401
from desktop.tests.window_support import look_file  # noqa: E402

ONE_WITHOUT_ITS_BAR = {"main": "classic", "day": "one", "options": {"one": {"daybar": "hide"}}}


def test_saved_looks_round_trip_with_surface(qapp: QApplication, material_window: NativeWindow) -> None:
    window = material_window
    window._look = wear(sanitize_look(None), NIGHT)
    window._saved_looks = save_look([], NIGHT, "Night study")
    window._layout = sanitize_layout(ONE_WITHOUT_ITS_BAR)
    window._surface = "material"
    window._save_look()
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert "surface" not in stored["layout"]
    assert stored["layout"]["options"]["one"]["daybar"] == "hide"
    assert stored["saved_looks"] == [NIGHT]
    assert stored["custom"] == NIGHT

    # A file from before Material 3 has no surface: the Widgets styles.
    aged = {key: value for key, value in stored.items() if key != "surface"}
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "widgets"
    assert window._saved_looks == [NIGHT]
    assert window._layout["options"]["one"]["daybar"] == "hide"
    assert window._look["custom"] == NIGHT

    # So is a surface nobody knows.
    aged["surface"] = "nope"
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "widgets"
    assert window._saved_looks == [NIGHT]

    # A surface buried in the layout is not the window's; the top-level one is read and kept out of it.
    aged["layout"]["surface"] = "material"
    aged["surface"] = "material"
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "material"
    assert "surface" not in window._layout
    assert window._saved_looks == [NIGHT]
    assert window._layout["options"]["one"]["daybar"] == "hide"


def test_setup_writes_material_beside_the_layout(qapp: QApplication, material_window: NativeWindow) -> None:
    window = material_window
    window._surface = "material"
    window._material_failed = ""
    window._material_gave_up = False
    answer = {
        "look": sanitize_look(window._look),
        "layout": sanitize_layout(ONE_WITHOUT_ITS_BAR),
        "pack": "system",
    }

    window._setup_step_left(0, 1, answer)

    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored["layout"]["main"] == "classic"
    assert stored["layout"]["options"]["one"]["daybar"] == "hide"
    assert "surface" not in stored["layout"]
    window._surface = "widgets"
    window._load_look()
    assert window._surface == "material"
    assert window._layout["options"]["one"]["daybar"] == "hide"
