# ruff: noqa: F811
"""What is left of look.py after the Widgets painting went: reading the stored look, the motion level a
look starts at, and the look file read and written back with every key the app writes."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native import cpu_drawing  # noqa: E402
from desktop.native.custom_look import save_look, wear  # noqa: E402
from desktop.native.layout_choice import sanitize_layout  # noqa: E402
from desktop.native.look import effective_look, look_motion, pack_axis, sanitize_look  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    look_file,
    qapp,  # noqa: F401
    window,  # noqa: F401
)

CUSTOM = {
    "name": "Night study",
    "base": "paper",
    "accent": "sea",
    "colours": {"page": "#1e2430", "card": "#262d3b", "text": "#e8ecf2", "line": "#394255"},
    "corners": 4,
    "heading_font": "mono",
    "text_scale": 1.2,
}


def look_of(preset: str, **knobs: str) -> dict:
    return {"preset": preset, "knobs": knobs}


def test_unknown_knobs_and_looks_fall_back_and_a_hand_edited_file_never_stops_the_look_loading() -> None:
    clean = sanitize_look({"preset": "neon", "knobs": {"font": "comic", "text": "large"}})
    assert clean["preset"] == "default"
    assert clean["knobs"] == {"text": "large"}
    assert effective_look(clean)["font"] == "sans"
    assert effective_look(clean)["text"] == "large"
    # A file edited by hand may hold anything; nothing in it can stop the look loading.
    odd = sanitize_look({"preset": ["poster"], "knobs": {"corners": ["round"], "depth": {"x": 1}}})
    assert odd == {"preset": "default", "knobs": {}}


def test_a_presets_knobs_come_first_and_the_students_own_knobs_win_over_them() -> None:
    effective = effective_look(sanitize_look(look_of("terminal", text="large")))
    assert effective["font"] == "mono"
    assert effective["corners"] == "sharp"
    assert effective["text"] == "large"


def test_a_look_saved_by_016_opens_with_its_knobs_named_as_017_names_them() -> None:
    """0.17 renamed five knob values. A look file written by 0.16 keeps what it chose: frost is
    Layered, round Soft, pill Round, flat depth None, hard Bold, outlined Outline."""
    saved = {
        "preset": "terminal",
        "knobs": {"surface": "frost", "corners": "pill", "depth": "hard", "blocks": "outlined"},
    }
    assert sanitize_look(saved)["knobs"] == {
        "surface": "layered",
        "corners": "rounded",
        "depth": "bold",
        "blocks": "outline",
    }
    assert sanitize_look({"knobs": {"corners": "round", "depth": "flat"}})["knobs"] == {
        "corners": "soft",
        "depth": "none",
    }
    # Today's names pass through unchanged, Round among them.
    assert sanitize_look({"knobs": {"corners": "rounded"}})["knobs"] == {"corners": "rounded"}


def test_the_frost_packs_are_the_axis_a_saved_preference_has_always_had() -> None:
    assert pack_axis("light-frost") == "slate"
    assert pack_axis("dark-frost") == "nocturne"
    assert pack_axis("system") == "system"
    assert pack_axis("no-such-pack") == "system"


def test_paper_starts_at_reduce_motion_and_every_other_look_at_normal() -> None:
    assert look_motion(look_of("paper")) == "reduce"
    for preset in ("default", "ink"):
        assert look_motion(look_of(preset)) == "normal", preset
    # A custom look's own level wins; one made on Paper without a level starts at Reduce.
    assert look_motion(wear(sanitize_look(None), {**CUSTOM, "motion": "extra"})) == "extra"
    assert look_motion(wear(sanitize_look(None), CUSTOM)) == "reduce"


def test_a_look_file_the_app_wrote_is_written_back_unchanged(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Every key the app writes, with a value that is not the default, and a key of Material's own that
    this build does not know inside the material object: read, then written, the file is the same."""
    window._look = wear(sanitize_look(look_of("ink", text="large")), CUSTOM)
    window._saved_looks = save_look([], CUSTOM, "Night study")
    window._layout = sanitize_layout(
        {"main": "classic", "day": "dial", "options": {"classic": {"look": "preset:paper"}}}
    )
    window._zoom = {"week.hours": 96}
    window._rail_month = False
    window._new_look_notice_seen = {"alpha", "beta"}
    window._new_look_notice_exempt = {"gamma"}
    window._cpu_drawing_version = "1.2.3"
    window._save_look()
    written = json.loads(look_file().read_text())
    for key in (
        "preset",
        "knobs",
        "custom",
        "surface",
        "layout",
        "updates",
        "zoom",
        "saved_looks",
        "rail",
        "new_look_notice_seen",
        "new_look_notice_exempt",
        cpu_drawing.LOOK_KEY,
    ):
        assert key in written, key
    written["material"] = {"surface": "tonal", "a_key_from_a_later_build": {"x": [1, 2]}}
    look_file().write_text(json.dumps(written) + "\n")

    window._look, window._saved_looks, window._zoom = {}, [], {}
    window._load_look()
    window._save_look()

    assert json.loads(look_file().read_text()) == written
