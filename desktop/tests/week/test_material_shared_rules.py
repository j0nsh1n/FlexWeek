"""Shared rules that only the Widgets screens used to prove, now held on Material: what its notice
shows and drops, the week title's short month names, and what a block drawn on the grid starts as."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.grid_support import PIANO, WEDNESDAY
from desktop.tests.week.support_material import (
    _bridge,
    _pump,
    _reset,
    _snack,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def _with_piano(qapp, window):
    root = _reset(window, qapp)
    window.session.add_block(dict(PIANO))
    window.session.save()
    settled(qapp, window)
    return root


def test_a_progress_message_never_shows_on_the_notice(qapp, window) -> None:
    _reset(window, qapp)
    window._telling = True
    window._on_status("Saving…")
    _pump(qapp, 10)
    assert _snack(window) == ""
    # The same call does show words that are not still going, so an empty notice above is the rule.
    window._telling = True
    window._on_status("Reloaded this week.")
    _pump(qapp, 10)
    assert _snack(window) == "Reloaded this week."


def test_duplicate_says_nothing_is_copied_and_then_what_it_duplicated(qapp, window) -> None:
    _with_piano(qapp, window)
    bridge = _bridge(window)
    bridge._clear_snack(bridge._snack)
    window.session._say("")
    bridge.week.duplicateBlock("piano", WEDNESDAY)
    _pump(qapp, 20)
    assert bridge.sheets.kind == "preview"
    assert "copied" not in window.session.message, "Duplicate leaves nothing copied, so it says nothing"
    assert "copied" not in _snack(window)
    bridge.sheets.savePreview()
    settled(qapp, window)
    assert _snack(window) == "Duplicated Piano."


def test_the_week_title_names_the_month_in_three_letters(qapp, window) -> None:
    _reset(window, qapp)
    window.session.load_week("2026-09-28")
    settled(qapp, window)
    window._material_page.publish()
    _pump(qapp, 10)
    assert _bridge(window).title == "28 Sep – 4 Oct"


def test_a_block_drawn_on_the_grid_is_not_school_by_default(qapp, window) -> None:
    _reset(window, qapp)
    assert window.session.armed_category is None
    sheets = _bridge(window).sheets
    sheets.openBlockAt(WEDNESDAY, 16 * 60, 17 * 60)
    _pump(qapp, 10)
    assert sheets._block.category != "class", "16:00 is after school"
    sheets.forceClose()


def test_a_notice_loses_its_undo_when_a_later_change_is_saved(qapp, window) -> None:
    _with_piano(qapp, window)
    bridge = _bridge(window)
    bridge._clear_snack(bridge._snack)
    bridge.week.moveBlock("piano", WEDNESDAY, WEDNESDAY, 17 * 60, 18 * 60)
    settled(qapp, window)
    _pump(qapp, 10)
    assert (bridge.snackAction, _snack(window)) == ("UNDO", "Moved Piano to Wed 17:00.")
    window.session.select_block("piano", WEDNESDAY)
    window.session.delete_selected()
    settled(qapp, window)
    _pump(qapp, 10)
    assert _snack(window) == "", "its Undo would now take back the delete"
