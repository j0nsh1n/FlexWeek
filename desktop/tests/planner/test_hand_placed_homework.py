# ruff: noqa: F811
"""Homework the student puts somewhere by hand: dropped on the calendar, chosen in a dialog, moved to
another day. It is pinned, it is one Undo step, and Replan all leaves it where it was put."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from desktop.native.widgets import ChooseTimeDialog, HomeworkDialog  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.blocks_helper import put_block  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    drop_chip,
    hours_of,
    press,
    qapp,  # noqa: F401
    settled,
    waiting_math,
    window,  # noqa: F401
)


def test_homework_moved_by_hand_to_another_day_is_saved_pinned(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The server accepts the pin, and it survives a reload."""
    work = next(block for block in window.session.blocks if block.get("assignment_id") == "essay")
    assert window.session.hand_move(work["id"], 3, 4, 19 * 60, 20 * 60)
    window.session.save()
    settled(qapp, window)
    window.session.load_week(window.session.week_start, discard=True)
    settled(qapp, window)
    moved = next(block for block in window.session.blocks if block["id"] == work["id"])
    assert (moved["days"], moved["start"], moved.get("pinned")) == ([4], "19:00", True)


def test_homework_dropped_on_the_calendar_gets_that_time_and_keeps_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    waiting = waiting_math(qapp, window)
    assert not waiting.get("start")
    # Friday: the clock is Thursday 19:00, and a drop on a day already past is refused.
    drop_chip(qapp, window, waiting["id"], "16:00", 4)
    settled(qapp, window)
    placed = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert (placed["days"], placed["start"], placed.get("pinned")) == ([4], "16:00", True)
    window.session.undo()
    settled(qapp, window)
    back = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert not back.get("start"), "the drop is one Undo step"
    window.session.redo()
    settled(qapp, window)
    window.session.solve(everything=True)
    settled(qapp, window)
    replanned = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert (replanned["days"], replanned["start"]) == ([4], "16:00"), "Replan all leaves it where it was put"


def test_a_drop_over_school_sits_beside_it_and_no_plan_moves_it_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Two blocks at one time is allowed, side by side, and said. It was put there by hand, so the
    planner that makes way for School leaves it where it is."""
    waiting = waiting_math(qapp, window)
    # Friday's School: the clock is Thursday 19:00, and a drop on a day already past is refused.
    drop_chip(qapp, window, waiting["id"], "10:00", 4)
    settled(qapp, window)
    placed = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert (placed["days"], placed["start"], placed.get("pinned")) == ([4], "10:00", True)
    hours = hours_of(window)
    friday = {item.block_id: item.columns for item, _rect in hours.drawn(hours.track_for(4, 10 * 60))}
    assert friday == {"school": 2, waiting["id"]: 2}, "side by side, each marked"
    window.session.solve(everything=True)
    settled(qapp, window)
    replanned = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert (replanned["days"], replanned["start"]) == ([4], "10:00")


def test_choose_a_time_places_homework_without_dragging(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """For the keyboard, and for the designs with no grid to drop on."""
    waiting = waiting_math(qapp, window)
    seen: list[str] = []

    def pick(dialog: ChooseTimeDialog) -> int:
        # The clock is held at Thursday, so that is where it opens, not on Monday.
        seen.append(f"opened on {dialog.day.currentData()}")
        # Friday, ahead of the clock: a time already past is refused.
        dialog.day.setCurrentIndex(dialog.day.findData(4))
        dialog.start.setTime(QTime(10, 0))
        seen.append(dialog.beside.text())
        ok = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
        seen.append("ok" if ok.isEnabled() else "refused")
        dialog.start.setTime(QTime(16, 7))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ChooseTimeDialog, "exec", pick)
    monkeypatch.setattr(HomeworkDialog, "exec", lambda dialog: press(dialog, "homeworkChooseTime"))
    window._edit_homework("math")
    settled(qapp, window)
    assert seen == [
        "opened on 3",
        "School is at that time too. Both will show, side by side.",
        "ok",
    ]
    placed = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert (placed["days"], placed["start"], placed.get("pinned")) == ([4], "16:07", True), "the time picked"
    hours = hours_of(window)
    shown = next(
        item for item, _rect in hours.drawn(hours.track_for(4, 16 * 60)) if item.block_id == waiting["id"]
    )
    assert "Pinned" in shown.detail


def test_let_flexweek_move_it_takes_the_pin_away(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    waiting = waiting_math(qapp, window)
    put_block(window.session, waiting["id"], 2, 17 * 60, 17 * 60 + waiting["duration_min"], pinned=True)
    window.session.save()
    settled(qapp, window)
    monkeypatch.setattr(HomeworkDialog, "exec", lambda dialog: press(dialog, "homeworkUnpin"))
    window._edit_homework("math")
    settled(qapp, window)
    released = next(block for block in window.session.blocks if block["id"] == waiting["id"])
    assert released.get("pinned") is None and released["start"] == "17:00"
