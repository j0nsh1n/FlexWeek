"""Material's "finish the block when the timer runs out" rule: it finishes only the session that ran, and
the homework only when that was its last session. Expected values are the app's and the spec's, not read
back from the code."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.focus.support_focus_screen import (  # noqa: F401
    block_named,
    homework,
    material_focus_window,
    rules,
    run_out,
    settled,
    start,
)
from desktop.tests.window_support import qapp  # noqa: F401


def test_auto_complete_finishes_only_the_session_that_ran_and_leaves_the_homework_open(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    blocks = homework(qapp, window, "lab", 2)
    first, second = blocks
    with rules(window, focus_auto_complete=True):
        assert start(window, first)
        run_out(qapp, window)
        done = block_named(window, first["id"])
        assert done["completed"] is True and done["completed_day"] == first["days"][0]
        assert not block_named(window, second["id"]).get("completed")
        assert not window.session.assignments["lab"].get("completed")


def test_auto_complete_finishes_the_homework_too_when_that_was_its_last_session(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    only = homework(qapp, window, "poem", 1)[0]
    with rules(window, focus_auto_complete=True):
        assert start(window, only)
        run_out(qapp, window)
        assert block_named(window, only["id"])["completed"] is True
        assert window.session.assignments["poem"]["completed"] is True


def test_the_last_of_two_sessions_finishes_the_homework_after_the_first_left_it_open(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    first, second = homework(qapp, window, "maps", 2)
    with rules(window, focus_auto_complete=True):
        assert start(window, first)
        run_out(qapp, window)
        assert not window.session.assignments["maps"].get("completed")
        window.session.reset_focus()
        assert start(window, second)
        run_out(qapp, window)
        assert block_named(window, second["id"])["completed"] is True
        assert window.session.assignments["maps"]["completed"] is True


@pytest.mark.parametrize(
    ("owned", "prefs"),
    [
        (True, {}),  # the setting is off by default
        (True, {"focus_auto_complete": False}),
        (False, {"focus_auto_complete": True}),  # a Widgets style never finishes a block by itself
    ],
)
def test_nothing_is_finished_unless_the_rule_is_on_in_material(
    qapp: QApplication, material_focus_window: NativeWindow, owned: bool, prefs: dict
) -> None:
    window = material_focus_window
    only = homework(qapp, window, "quiet", 1)[0]
    with rules(window, owned, **prefs):
        assert start(window, only)
        run_out(qapp, window)
        assert not block_named(window, only["id"]).get("completed")
        assert not window.session.assignments["quiet"].get("completed")


def test_a_quick_focus_has_no_block_to_finish_and_does_not_fail(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    with rules(window, focus_auto_complete=True):
        assert window.session.start_quick_focus()
        run_out(qapp, window)
        assert window.session.focus is not None  # on to its break, as before


def test_skip_does_not_auto_complete_the_block(
    qapp: QApplication, material_focus_window: NativeWindow
) -> None:
    window = material_focus_window
    only = homework(qapp, window, "skipme", 1)[0]
    with rules(window, focus_auto_complete=True):
        assert start(window, only)
        window.session.advance_focus(False)
        settled(qapp, window)
        assert window.session.focus["phase"] == "break"
        assert not block_named(window, only["id"]).get("completed")
        assert not window.session.assignments["skipme"].get("completed")
