"""What a drag on the hours makes, and what the notice says once it is saved."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, timedelta

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_drag import (
    LEFT,
    answer_editors,
    create_on,
    drag,
    notice,
    open_thursday,
    qapp,  # noqa: F401
    send,
    session_of,
    settled,
    toast,
    tray_chip,
    window,  # noqa: F401
)


def test_a_block_made_by_dragging_guesses_its_category_from_when_it_starts(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It used to be School, so an hour of Club counted as School in the Day's summary. Add fixed time
    guesses from the time of day (#52): 16:00 is after school and no meal, so Activity. A type picked
    under Add, "Then drag on the calendar", is still what the next drag makes."""
    seen = answer_editors(monkeypatch, "Club", None, "Practice")
    add = window.findChild(QPushButton, "addButton")
    day = open_thursday(qapp, window)
    says = [add.text()]
    create_on(qapp, window, day, 3, "16:00-17:00", "Club")
    window.add_menu.findChild(QAction, "addMenu-exercise").trigger()
    settled(qapp, window)
    says.append(add.text())
    create_on(qapp, window, day, 3, "17:30-18:00", "Practice")
    made = {
        block["title"]: (block["days"], block["start"], block["duration_min"], block.get("category"))
        for block in window.session.blocks
        if block["title"] in ("Club", "Practice")
    }
    assert (says, seen, made, window.day_view.summary.text()) == (
        ["Add", "Add sports"],
        [("", "Activity"), ("Sports", "Sports"), ("Sports", "Sports")],
        {"Club": ([3], "16:00", 60, "extra"), "Practice": ([3], "17:30", 30, "exercise")},
        "School: 6 h 30 min\nActivity: 1 h 30 min\nSports: 30 min\nHomework: 1 h",
    )


def test_a_move_a_resize_a_create_and_a_placing_each_say_what_they_did_with_undo(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dragging saved at once with no sign. Now each change says what it did once it is saved, with
    Undo beside it, and Undo takes that one change back and says so."""
    session = window.session
    answer_editors(monkeypatch, "Club")
    hours = window.week_table.hours
    math = session_of(window, "math")["id"]
    said = []

    hours.reveal(3, 17 * 60, 21 * 60)
    qapp.processEvents()
    drag(qapp, hours, hours, hours.point_for(3, 19 * 60 + 30), hours.point_for(4, 18 * 60 + 30))
    wait_until(qapp, lambda: session_of(window, "essay")["days"] == [4])
    settled(qapp, window)
    said.append(notice(window))

    hours.reveal(4, 17 * 60, 21 * 60)
    qapp.processEvents()
    # Three pixels inside the essay's end, where a press resizes it.
    edge = QPoint(0, -3)
    drag(qapp, hours, hours, hours.point_for(4, 19 * 60) + edge, hours.point_for(4, 19 * 60 + 30) + edge)
    wait_until(qapp, lambda: session_of(window, "essay")["duration_min"] == 90)
    settled(qapp, window)
    said.append(notice(window))

    create_on(qapp, window, hours, 5, "10:00-11:00", "Club")
    said.append(notice(window))

    hours.reveal(3, 17 * 60, 20 * 60)
    qapp.processEvents()
    before = [dict(block) for block in session.blocks]
    drag(
        qapp,
        tray_chip(window, math),
        hours,
        tray_chip(window, math).mapToGlobal(QPoint(8, 8)),
        hours.point_for(3, 18 * 60),
    )
    wait_until(qapp, lambda: session_of(window, "math").get("start") == "18:00")
    settled(qapp, window)
    said.append(notice(window))
    assert said == [
        (True, "Moved History essay to Fri 6:00 PM.", "Undo"),
        (True, "History essay now ends at 7:30 PM.", "Undo"),
        (True, "Added Club on Sat 10:00 AM.", "Undo"),
        (True, "Placed Math worksheet on Thu 6:00 PM.", "Undo"),
    ]

    QTest.mouseClick(window.findChild(QPushButton, "toastButton"), LEFT)
    wait_until(qapp, lambda: not session_of(window, "math").get("start"))
    settled(qapp, window)
    assert (notice(window), toast(window)) == ((False, "", ""), "Undid placing Math worksheet.")
    assert session.blocks == before, "Undo took back the placing and nothing else"


def test_the_notice_waits_for_the_pointer_and_goes_once_its_change_is_no_longer_the_last(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Nothing new appears under a held block, so a notice that lands while one is held waits for it
    to be let go. Once a later change is saved, its Undo would take back that one instead, so it
    goes."""
    session = window.session
    hours = window.week_table.hours
    hours.reveal(3, 16 * 60, 21 * 60)
    qapp.processEvents()
    session.client.hold()
    drag(qapp, hours, hours, hours.point_for(3, 19 * 60 + 30), hours.point_for(3, 20 * 60 + 30))
    assert session.busy, "the essay's save is still on its way"
    # The chips the release took out of the tray are freed before a hand could press again. Freed
    # while a block is held, each is a window of its own going, which lets the block go.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    # Held on Piano while the essay's save lands.
    send(hours, QEvent.Type.MouseButtonPress, hours.point_for(3, 17 * 60 + 15), True)
    send(hours, QEvent.Type.MouseMove, hours.point_for(3, 17 * 60 + 45), True)
    session.client.release()
    wait_until(qapp, lambda: not session.busy and session_of(window, "essay")["start"] == "20:00")
    held = notice(window)
    # Read before Piano's own save lands and says what it did.
    session.client.hold()
    send(hours, QEvent.Type.MouseButtonRelease, hours.point_for(3, 17 * 60 + 45), False)
    qapp.processEvents()
    let_go = notice(window)
    session.client.release()
    wait_until(qapp, lambda: next(b for b in session.blocks if b["id"] == "piano")["start"] == "17:30")
    settled(qapp, window)
    after_piano = notice(window)
    session.select_block("piano", 3)
    QTest.keyClick(window, Qt.Key.Key_Delete)
    settled(qapp, window)
    assert (held, let_go, after_piano, notice(window)) == (
        (False, "", ""),
        (True, "Moved History essay to Thu 8:00 PM.", "Undo"),
        (True, "Moved Piano to Thu 5:30 PM.", "Undo"),
        (False, "", ""),
    )


def test_a_move_in_a_design_says_what_it_did_too(qapp: QApplication, window: NativeWindow) -> None:
    from desktop.native.layouts.registry import sanitize_layout

    window._layout = sanitize_layout({"main": "mission", "day": "one"})
    window._apply_appearance()
    window._on_week()
    settled(qapp, window)
    hours = window.planner.currentWidget().hours_surfaces()[0]
    hours.reveal(3, 17 * 60, 21 * 60)
    qapp.processEvents()
    drag(qapp, hours, hours, hours.point_for(3, 19 * 60 + 30), hours.point_for(4, 18 * 60 + 30))
    wait_until(qapp, lambda: session_of(window, "essay")["days"] == [4])
    settled(qapp, window)
    assert notice(window) == (True, "Moved History essay to Fri 6:00 PM.", "Undo")


def test_a_chip_carried_on_month_says_what_it_did(qapp: QApplication, window: NativeWindow) -> None:
    # Inside the offscreen screen, 800 pixels square, where the hand can find the date under a point.
    window.move(0, 0)
    window.resize(760, 720)
    QTest.mouseClick(window.findChild(QAbstractButton, "viewMonth"), LEFT)
    settled(qapp, window)
    canvas = window.month_grid.canvas
    thursday = date.fromisoformat(window.session.week_start) + timedelta(days=3)
    friday = thursday + timedelta(days=1)
    canvas.reveal(thursday.isoformat())
    qapp.processEvents()
    essay = session_of(window, "essay")["id"]
    start, end = canvas.chip_point(essay, thursday.isoformat()), canvas.cell_point(friday.isoformat())
    drag(qapp, canvas, canvas, start, end)
    wait_until(qapp, lambda: session_of(window, "essay")["days"] == [4])
    settled(qapp, window)
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    words = f"Moved History essay to Fri {friday.day} {months[friday.month - 1]}."
    assert notice(window) == (True, words, "Undo")


def test_a_save_that_leaves_the_homework_waiting_keeps_the_same_chips(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Chips made again on every save were shown a frame after the old ones went, so Today's app's
    "Needs a time" bar blinked empty each time a block moved."""
    before = tray_chip(window, session_of(window, "math")["id"])
    essay = session_of(window, "essay")
    window._move_block(essay["id"], 3, 4, 18 * 60, 19 * 60)
    settled(qapp, window)
    after = tray_chip(window, session_of(window, "math")["id"])
    assert after is before, "the Needs a time bar made its chips again for the same homework"
    assert after.isVisible()
