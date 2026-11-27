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


def test_a_material_save_writes_the_look_file_as_python_always_did(tmp_path) -> None:  # noqa: ANN001
    """Saving Material puts it in place and leaves every other key's bytes as json.dumps wrote them:
    the spaces after ':' and ',', escaped non-ASCII, and Python's number spelling."""
    from desktop.native.material.theme import kept_material, store_material

    path = tmp_path / "look.json"
    before = {
        "preset": "high-contrast",
        "saved_looks": [{"name": "Caf\u00e9 night", "scale": 1.1}],
        "layout": {"main": "classic", "day": "dial", "options": {}},
        "material": {"preset": "Slate"},
        "zoom": {"week.hour": 1.25},
        "extra": {"nested": [1, 2.5, "\u00fc"]},
    }
    path.write_text(json.dumps(before) + "\n", encoding="utf-8")
    material = {"preset": "Blue", "mode": "dark"}
    store_material(path, material)
    after = dict(before, material=material)
    assert path.read_text(encoding="utf-8") == json.dumps(after) + "\n"
    assert kept_material(path) == material


def test_a_look_file_that_is_not_text_reads_as_empty(tmp_path) -> None:  # noqa: ANN001
    from desktop.native.material.theme import kept_material, store_material

    path = tmp_path / "look.json"
    path.write_bytes(b"\xff\xfe not utf-8")
    assert kept_material(path) is None
    store_material(path, {"preset": "Slate"})
    assert path.read_text(encoding="utf-8") == json.dumps({"material": {"preset": "Slate"}}) + "\n"
