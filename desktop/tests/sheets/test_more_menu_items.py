# ruff: noqa: F811
"""The More menu: the same two buttons in every design, the headings and items it groups, and an item doing
what its button does."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    SPOTIFY_TRACK,
    more_actions,
    more_sections,
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)


def test_plan_and_more_stay_on_the_bar_in_every_layout(qapp: QApplication, window: NativeWindow) -> None:
    """A design of its own used to hide Plan my homework and More behind Tools. That rule is gone: the
    same two buttons stay in the top bar in every layout, every view, and My day."""
    assert window.findChild(QPushButton, "toolsButton") is None
    sections = None
    items = None
    for main in ("classic", "bento", "timeline"):
        window._layout = {"main": main, "day": "one", "options": {}}
        window._on_week()
        assert window.solve_button.isVisible() is True
        assert window.more_button.isVisible() is True
        assert window.more_button.text() == "More"
        if sections is None:
            sections, items = more_sections(window), set(more_actions(window))
        else:
            assert more_sections(window) == sections
            assert set(more_actions(window)) == items
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    offered = more_actions(window)
    # Every group under a heading.
    assert more_sections(window) == ["Planning", "Edit", "Help and info", "Account"]
    assert not {"Add homework", "Add fixed time", "School hours"} & set(offered), "adding is under Add"
    wanted = {
        "Running late",
        "Routines",
        "Reload this week",
        "Undo",
        "Redo",
        "Undo, copy and save",
        "Sign out",
    }
    assert wanted <= set(offered)
    assert "Settings" not in offered
    assert "Account" not in offered
    assert (offered["Undo"], offered["Redo"]) == (True, False)


def test_more_groups_what_the_toolbar_does_not_keep(qapp: QApplication, window: NativeWindow) -> None:
    sections = more_sections(window)
    items = more_actions(window)
    assert sections == ["Planning", "Edit", "Help and info", "Account"]
    wanted = {
        "Undo",
        "Redo",
        "Duplicate",
        "Running late",
        "Routines",
        "Week as a list",
        "Undo, copy and save",
        "Sign out",
    }
    assert wanted <= set(items)
    assert "Settings" not in items
    assert "Account" not in items
    assert "Replan all my homework" in items


def test_a_more_item_does_what_its_button_does(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    before = len(window.session.blocks)
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    advanced = next(action.menu() for action in menu.actions() if action.text() == "Undo, copy and save")
    next(action for action in advanced.actions() if action.text() == "Undo").trigger()
    settled(qapp, window)
    assert len(window.session.blocks) != before or window.session.can_redo() is True


def test_more_hides_spotify_until_there_is_a_link(qapp: QApplication, window: NativeWindow) -> None:
    assert "Open Spotify link" not in more_actions(window)
    window.session.preferences = {
        **(window.session.preferences or {}),
        "default_spotify_url": SPOTIFY_TRACK,
    }
    assert "Open Spotify link" in more_actions(window)


def test_retros_start_opens_mores_menu(qapp: QApplication, window: NativeWindow) -> None:
    """Start is the app's own menu, More's: it asks for nothing More does not already offer. (That it
    opens up from the taskbar is a picture: week.retro_start_menu_opens_up.)"""
    window._layout = sanitize_layout({"main": "retro", "day": "one"})
    window._day_mode = False
    window.session.set_view("week")
    window._on_week()
    qapp.processEvents()
    start = window.planner.currentWidget().findChild(QPushButton, "retroStart")
    start.click()
    wait_until(qapp, window.more_menu.isVisible)
    window.more_menu.close()
