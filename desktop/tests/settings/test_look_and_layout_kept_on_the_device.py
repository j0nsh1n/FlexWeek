# ruff: noqa: F811
"""The look, the layout choice and the student's own looks are kept in the look file on this computer
and read back as they were."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    look_file,
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_the_choice_is_saved_on_this_device_beside_the_look(qapp: QApplication, window: NativeWindow) -> None:
    window._look = {"preset": "paper", "knobs": {"corners": "rounded"}}
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"look": "preset:one-paper"}}}
    window._save_look()
    stored = json.loads(look_file().read_text())
    assert stored["preset"] == "paper"
    assert stored["knobs"] == {"corners": "rounded"}
    assert stored["layout"] == {
        "main": "classic",
        "day": "one",
        "options": {"one": {"look": "preset:one-paper"}},
    }
    # Whether this computer checks for updates lives beside the look, because it is a property of
    # the computer rather than the account.
    assert set(stored["updates"]) == {"check", "last_ms", "skip", "developer_builds"}
    window._look, window._layout = {}, {}
    window._load_look()
    assert window._look == {"preset": "paper", "knobs": {"corners": "rounded"}}
    assert window._layout["options"] == {"one": {"look": "preset:one-paper"}}


def test_a_look_file_from_before_layouts_still_loads(qapp: QApplication, window: NativeWindow) -> None:
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps({"preset": "terminal", "knobs": {}}))
    window._load_look()
    assert window._look["preset"] == "terminal"
    assert window._layout == {"main": "classic", "day": "dial", "options": {}}
    look_file().write_text("not json")
    window._load_look()
    assert window._layout == {"main": "classic", "day": "dial", "options": {}}


def test_saving_the_look_from_settings_keeps_the_layout(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"daybar": "hide"}}}
    window._look = {"preset": "ink", "knobs": {}}
    window._save_look()
    assert json.loads(look_file().read_text())["layout"]["options"] == {"one": {"daybar": "hide"}}


def test_a_custom_look_is_kept_with_the_saved_looks(qapp: QApplication, window: NativeWindow) -> None:
    """Customise end to end: Paper made a night look of the student's own, with Sea for the accent,
    School in green, square-ish corners, mono headings and larger text, saved by name in the look
    file and read back as it was."""
    from desktop.native.custom_look import save_look, wear
    from desktop.native.look import sanitize_look

    custom = {
        "name": "Night study",
        "base": "paper",
        "accent": "sea",
        "colours": {"page": "#1e2430", "card": "#262d3b", "text": "#e8ecf2", "line": "#394255"},
        "categories": {"class": {"hue": 140}},
        "corners": 4,
        "heading_font": "mono",
        "text_scale": 1.2,
    }
    window._look = wear(sanitize_look(None), custom)
    window._saved_looks = save_look([], custom, "Night study")
    window._layout = sanitize_layout(
        {**window._layout, "options": {**window._layout["options"], "classic": {"look": "your"}}}
    )
    window._apply_appearance()
    window._save_look()
    stored = json.loads(look_file().read_text())
    assert stored["custom"] == custom
    assert stored.get("saved_looks") == [custom], "the saved looks are not in the look file"
    window._look, window._saved_looks = {}, []
    window._load_look()
    assert window._look["custom"] == custom and window._saved_looks == [custom]
