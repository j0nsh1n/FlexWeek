"""The notice a change leaves on the Material week: what the advanced actions say, that a notice never
moves the hours, where it sits, and that a view switch keeps it with its Undo."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from desktop.tests.grid_support import PIANO, WEDNESDAY, hold_clock
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

PLACED_WORDS = "Moved History essay to Fri 18:00."


def _with_piano(qapp, window):
    root = _reset(window, qapp)
    window.session.add_block(dict(PIANO))
    window.session.save()
    settled(qapp, window)
    hold_clock(window, WEDNESDAY, 14 * 60 + 7)
    return root


def _do(qapp, window, act) -> None:
    act()
    _pump(qapp, 20)
    settled(qapp, window)


def _said_by_each_action(qapp, window) -> list[tuple[str, str]]:
    bridge = _bridge(window)
    said = []
    for words, act in (
        ("Copy", lambda: bridge.week.copyBlock("piano", WEDNESDAY)),
        ("Copy Wednesday", lambda: (bridge.sheets.openMore(), bridge.sheets.moreAction("copyDay"))),
        ("Undo", bridge.undo),
        ("Redo", bridge.redo),
        ("Reload this", lambda: (bridge.sheets.openMore(), bridge.sheets.moreAction("reloadWeek"))),
    ):
        window.session._say("")
        bridge._clear_snack(bridge._snack)
        _do(qapp, window, act)
        said.append((words, window.session.message, _snack(window)))
    return said


def test_every_advanced_action_says_what_it_did_in_the_session_words(qapp, window) -> None:
    _with_piano(qapp, window)
    assert [(words, message) for words, message, _snack_text in _said_by_each_action(qapp, window)] == [
        ("Copy", "Piano copied. Choose a destination and paste."),
        ("Copy Wednesday", "Wednesday · 2 items copied. Choose a destination and paste."),
        ("Undo", "Undid adding Piano."),
        ("Redo", "Redid adding Piano."),
        ("Reload this", "Reloaded this week."),
    ]


def test_every_advanced_action_shows_what_it_did_on_the_snackbar(qapp, window) -> None:
    _with_piano(qapp, window)
    shown = {words: text for words, _message, text in _said_by_each_action(qapp, window)}
    assert shown["Copy"] == "Piano copied. Choose a destination and paste."
    assert shown["Reload this"] == "Reloaded this week."


def test_a_notice_coming_and_going_never_moves_the_hours(qapp, window) -> None:
    """A notice in a row of its own pushed the page down under the pointer; the snackbar floats over."""
    root = _reset(window, qapp)
    grid = _qml(root, "weekScroller")
    before = (grid.property("x"), grid.property("y"), grid.property("width"), grid.property("height"))
    _bridge(window).note(PLACED_WORDS)
    _pump(qapp, 10)
    assert _snack(window) == PLACED_WORDS
    assert (grid.property("x"), grid.property("y"), grid.property("width"), grid.property("height")) == before
    _bridge(window)._clear_snack(PLACED_WORDS)
    _pump(qapp, 10)
    assert (grid.property("x"), grid.property("y"), grid.property("width"), grid.property("height")) == before


@pytest.mark.parametrize("height", [860, 600])
def test_the_snackbar_sits_inside_the_window_clear_of_the_rail_and_its_undo_takes_a_click(
    qapp, window, height: int
) -> None:
    root = _reset(window, qapp)
    window.resize(1280, height)
    _pump(qapp, 20)
    _bridge(window).note(PLACED_WORDS)
    _pump(qapp, 30)
    bar = _qml(root, "materialSnackbar")
    rail = _qml(root, "materialRail")
    top_left = bar.mapToScene(bar.boundingRect().topLeft())
    bottom_right = bar.mapToScene(bar.boundingRect().bottomRight())
    assert top_left.x() >= rail.mapToScene(rail.boundingRect().bottomRight()).x(), "clear of the rail"
    assert top_left.y() >= 0 and bottom_right.y() <= window._material_page._quick.height(), height
    assert bottom_right.x() <= window._material_page._quick.width()
    _click(window, bar, dx=int(bar.property("width")) // 2 - 30)
    settled(qapp, window)
    assert _snack(window) != PLACED_WORDS, "its Undo takes a click and the notice goes"
    assert str(_bridge(window).property("snackAction")) == "", "what Undo says carries no Undo of its own"


def test_a_view_switch_keeps_the_snackbar_and_its_undo(qapp, window) -> None:
    """0.18.5 #97: the Undo notice vanished on the first view switch. It stays through Day, Month and Week."""
    _reset(window, qapp)
    bridge = _bridge(window)
    bridge.note(PLACED_WORDS)
    _pump(qapp, 10)
    for screen in ("month", "day", "week"):
        bridge.showPage(screen)
        _pump(qapp, 15)
        assert _snack(window) == PLACED_WORDS and str(bridge.property("snackAction")) == "UNDO", screen


def test_a_routine_save_says_nothing_on_the_snackbar(qapp, window) -> None:
    _reset(window, qapp)
    _bridge(window)._clear_snack(_snack(window))
    for words in ("Saving…", "Saved.", "Saved preferences."):
        window.session._say(words)
    _pump(qapp, 10)
    assert _snack(window) == ""


def test_a_refusal_says_why_on_the_snackbar(qapp, window) -> None:
    _reset(window, qapp)
    window.session._say("Select a block before copying it.")
    _pump(qapp, 10)
    assert _snack(window) == "Select a block before copying it."
