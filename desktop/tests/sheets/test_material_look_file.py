# ruff: noqa: F811
"""The look file keeps the surface (always Material 3) beside, not inside, the layout, and an old or odd
file, the Widgets value included, opens Material. Its other keys are read as they were.
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.custom_look import save_look, wear  # noqa: E402
from desktop.native.layout_choice import sanitize_layout  # noqa: E402
from desktop.native.look import sanitize_look  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import NIGHT, material_window, qapp  # noqa: E402, F401
from desktop.tests.window_support import look_file  # noqa: E402

CLASSIC_PAPER = {"main": "classic", "day": "dial", "options": {"classic": {"look": "preset:paper"}}}


def test_saved_looks_round_trip_with_surface(qapp: QApplication, material_window: NativeWindow) -> None:
    window = material_window
    window._look = wear(sanitize_look(None), NIGHT)
    window._saved_looks = save_look([], NIGHT, "Night study")
    window._layout = sanitize_layout(CLASSIC_PAPER)
    window._surface = "material"
    window._save_look()
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert "surface" not in stored["layout"]
    assert stored["layout"]["options"]["classic"]["look"] == "preset:paper"
    assert stored["saved_looks"] == [NIGHT]
    assert stored["custom"] == NIGHT

    # A file from before Material 3 has no surface: Material.
    aged = {key: value for key, value in stored.items() if key != "surface"}
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "material"
    assert window._saved_looks == [NIGHT]
    assert window._layout["options"]["classic"]["look"] == "preset:paper"
    assert window._look["custom"] == NIGHT

    # So is a surface nobody knows, and the Widgets value an older build wrote.
    for old in ("nope", "widgets"):
        aged["surface"] = old
        look_file().write_text(json.dumps(aged))
        window._load_look()
        assert window._surface == "material"
    assert window._saved_looks == [NIGHT]

    # A surface buried in the layout is not the window's; the top-level one is read and kept out of it.
    aged["layout"]["surface"] = "material"
    aged["surface"] = "material"
    look_file().write_text(json.dumps(aged))
    window._load_look()
    assert window._surface == "material"
    assert "surface" not in window._layout
    assert window._saved_looks == [NIGHT]
    assert window._layout["options"]["classic"]["look"] == "preset:paper"


def test_setup_writes_material_beside_the_layout(qapp: QApplication, material_window: NativeWindow) -> None:
    window = material_window
    window._surface = "material"
    window._cpu_drawing_version = ""
    window._material_gave_up = False
    answer = {
        "look": sanitize_look(window._look),
        "layout": sanitize_layout(CLASSIC_PAPER),
        "pack": "system",
    }

    window._setup_step_left(0, 1, answer)

    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored["layout"]["main"] == "classic"
    assert stored["layout"]["options"]["classic"]["look"] == "preset:paper"
    assert "surface" not in stored["layout"]
    window._surface = "widgets"
    window._load_look()
    assert window._surface == "material"
    assert window._layout["options"]["classic"]["look"] == "preset:paper"
