"""Undo and Redo say what they undid: undoing an add says adding, undoing a change says editing.

Expected words come from the 0.19.0 wording audit (finding 2), not from the code's output.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import essay, fixed
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_undo_and_redo_of_an_added_block_say_adding_and_of_a_changed_one_say_editing(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    block = fixed("school", "School", 0, "08:00")
    session.add_block(block)
    session.save()
    settled(qapp, window)
    session.undo()
    settled(qapp, window)
    assert session.message == "Undid adding School."
    session.redo()
    settled(qapp, window)
    assert session.message == "Redid adding School."
    session.add_block({**block, "title": "Lessons"})
    session.save()
    settled(qapp, window)
    session.undo()
    settled(qapp, window)
    assert session.message == "Undid editing Lessons."


def test_undo_of_new_homework_says_adding_and_of_a_changed_one_says_editing(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    session.add_homework(essay(session))
    session.save()
    settled(qapp, window)
    session.undo()
    settled(qapp, window)
    assert session.message == "Undid adding Essay."
    session.redo()
    settled(qapp, window)
    session.add_homework({**session.assignments["essay"], "notes": "Cite two sources"})
    session.save()
    settled(qapp, window)
    session.undo()
    settled(qapp, window)
    assert session.message == "Undid editing Essay."
