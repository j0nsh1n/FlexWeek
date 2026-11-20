"""Paste and Duplicate show their preview on Material's own sheet, with the Widgets words, and Save puts the
rows in the week with the Widgets notice."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.grid_support import PIANO, WEDNESDAY, hold_clock
from desktop.tests.sheets.support_material_sheets import find
from desktop.tests.week.support_material import (
    _bridge,
    _click,
    _pump,
    _qml,
    _reset,
    _snack,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _with_copied_piano(qapp, window):
    root = _reset(window, qapp)
    window.session.add_block(dict(PIANO))
    window.session.save()
    settled(qapp, window)
    hold_clock(window, WEDNESDAY, 8 * 60)
    window.session.select_block("piano", WEDNESDAY)
    _bridge(window).week.copyBlock("piano", WEDNESDAY)
    settled(qapp, window)
    return root


def _titles(window) -> list[str]:
    return [block["title"] for block in window.session.blocks]


def test_paste_previews_on_a_material_sheet_and_save_adds_the_block(qapp, window) -> None:
    root = _with_copied_piano(qapp, window)
    before = len(window.session.blocks)
    _bridge(window).week.pasteHere(WEDNESDAY, 17 * 60)
    _pump(qapp, 20)
    sheets = _bridge(window).sheets
    assert sheets.kind == "preview"
    assert sheets.form["heading"] == "Preview paste"
    assert sheets.form["intro"] == "Nothing changes until you choose Paste."
    assert sheets.form["confirm"] == "Paste"
    assert len(window.session.blocks) == before, "nothing changes until the preview is saved"
    _click(window, _qml(root, "previewSave"))
    settled(qapp, window)
    assert sheets.kind == ""
    assert len(window.session.blocks) == before + 1
    assert _snack(window).startswith("Pasted Piano")


def test_cancel_and_unticking_save_nothing(qapp, window) -> None:
    root = _with_copied_piano(qapp, window)
    before = len(window.session.blocks)
    sheets = _bridge(window).sheets
    _bridge(window).week.pasteHere(WEDNESDAY, 17 * 60)
    _pump(qapp, 20)
    _click(window, find(root, "previewInclude0"))
    _pump(qapp, 10)
    assert sheets.form["canSave"] is False
    assert sheets.form["whyOff"] == "Select at least one item before saving."
    assert _qml(root, "previewSave").property("enabled") is False
    _click(window, _qml(root, "previewCancel"))
    settled(qapp, window)
    assert sheets.kind == ""
    assert len(window.session.blocks) == before


def test_duplicate_previews_the_same_way(qapp, window) -> None:
    root = _with_copied_piano(qapp, window)
    before = len(window.session.blocks)
    _bridge(window).week.duplicateBlock("piano", WEDNESDAY)
    _pump(qapp, 20)
    sheets = _bridge(window).sheets
    assert sheets.kind == "preview"
    _click(window, _qml(root, "previewSave"))
    settled(qapp, window)
    assert len(window.session.blocks) == before + 1
    assert _snack(window).startswith("Duplicated")


def test_a_fixed_time_can_be_moved_in_the_preview_before_it_is_saved(qapp, window) -> None:
    _with_copied_piano(qapp, window)
    sheets = _bridge(window).sheets
    _bridge(window).week.pasteHere(WEDNESDAY, 17 * 60)
    _pump(qapp, 20)
    row = sheets.form["rows"][0]
    assert row["fixed"] and row["start"] == "17:00" and row["day"] == WEDNESDAY
    sheets.previewStart(0, "18:30")
    sheets.previewDay(0, WEDNESDAY + 1)
    sheets.previewLength(0, 45)
    _pump(qapp, 10)
    moved = sheets.form["rows"][0]
    assert (moved["start"], moved["day"], moved["duration"]) == ("18:30", WEDNESDAY + 1, 45)
    sheets.savePreview()
    settled(qapp, window)
    pasted = [b for b in window.session.blocks if b["title"] == "Piano" and b["id"] != "piano"]
    assert [(block["start"], block["days"], block["duration_min"]) for block in pasted] == [
        ("18:30", [WEDNESDAY + 1], 45)
    ]
