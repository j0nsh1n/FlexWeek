# ruff: noqa: F811
"""Finishing homework from the Material Day screen: it moves to Done, Undo brings it back, it waits
for a save still on its way, and the line the snackbar shows clears itself.

Thursday 17:00: School 08:00-14:30 is over, the History essay waits at 18:45.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import root_bridge, rows_of, seed_thursday  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, show_material  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=17)


def test_finishing_homework_moves_it_to_done_and_undo_brings_it_back(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    day = bridge.property("day")
    assert day.property("leftLine") == "1 thing left today"
    day.finishHomework("essay")
    settled(qapp, window)
    pump(qapp)
    assert day.property("leftLine") == "Nothing left today"
    assert [row["title"] for row in rows_of(day.property("upNext"))] == []
    assert [row["title"] for row in rows_of(day.property("doneRows"))] == ["School", "History essay"]
    assert day.property("showNow") is False
    assert bridge.property("snackText") == "Finished History essay"
    bridge.undo()
    settled(qapp, window)
    pump(qapp)
    assert day.property("leftLine") == "1 thing left today"
    assert [row["title"] for row in rows_of(day.property("upNext"))] == ["History essay"]
    assert bridge.property("snackText") == ""


def test_finishing_homework_waits_while_a_save_is_pending(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    session.client.hold()
    try:
        session.add_homework(
            {
                "id": "busy-check",
                "title": "Busy check",
                "due": sunday_due(session.week_start),
                "estimate_min": 30,
                "revision": 0,
            }
        )
        session.save()
        assert session.busy, "the save must still be on its way, or this tests nothing"
        day.finishHomework("essay")
        assert session.assignments["essay"].get("completed") is not True
        assert root_bridge(root).property("snackText") == (
            "Saving your last change… That check will work in a moment."
        )
    finally:
        session.client.release()
        settled(qapp, window)


def test_a_snackbar_line_clears_itself_but_not_a_newer_one(qapp: QApplication, window: NativeWindow) -> None:
    bridge = root_bridge(show_material(qapp, window))
    bridge.note("First line")
    bridge.note("Second line")
    bridge._clear_snack("First line")
    assert bridge.property("snackText") == "Second line"
    bridge._clear_snack("Second line")
    assert bridge.property("snackText") == ""
