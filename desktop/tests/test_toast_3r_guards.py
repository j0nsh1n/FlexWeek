# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import re
from copy import deepcopy

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest

from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)
from desktop.tests.regress184.test_regress_item3_plan_undo_toast import planned


def test_toast_uses_pointer_geometry_over_untracked_page(qapp, window) -> None:
    under = window.centralWidget()
    assert not under.hasMouseTracking()
    toast = window.toast
    toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    settled(qapp, window)
    point = toast.card.mapToGlobal(toast.card.rect().center())
    QCursor.setPos(point)
    toast._poll_state()
    assert toast._over_point(point)
    assert toast._pointer


@pytest.mark.parametrize(
    ("key", "unavailable"),
    [("visible", False), ("minimized", True), ("active", False)],
    ids=["hidden", "minimized", "inactive"],
)
def test_toast_holds_remaining_time_while_window_is_unavailable(
    qapp, window, monkeypatch, key, unavailable
) -> None:
    state = {"visible": True, "minimized": False, "active": True}
    monkeypatch.setattr(window, "isVisible", lambda: state["visible"])
    monkeypatch.setattr(window, "isMinimized", lambda: state["minimized"])
    monkeypatch.setattr(window, "isActiveWindow", lambda: state["active"])
    toast = window.toast
    toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    toast._pointer = False
    toast._sync_pause()
    left = toast._left_ms()
    state[key] = unavailable
    toast._sync_pause()
    assert toast._paused and abs(toast._held_ms - left) <= 50
    QTest.qWait(1200)
    assert toast._left_ms() == left
    state[key] = not unavailable
    toast._sync_pause()
    assert not toast._paused and toast._timer.remainingTime() >= left - 250


def test_toast_announces_once_and_politely(qapp, window, monkeypatch) -> None:
    announcements = []
    monkeypatch.setattr(
        "desktop.native.widgets.announce",
        lambda widget, words, *, assertive=False: announcements.append((widget, words, assertive)),
    )
    window.toast.show_message("Placed 1 homework block.", "Undo", lambda: None)
    assert announcements == [(window.toast, "Placed 1 homework block.", False)]


@pytest.mark.parametrize("mode", ["joined-save", "queued-save", "auto-split"])
def test_replan_offers_undo_for_the_changes_it_placed(qapp, window, mode) -> None:
    session = window.session
    if mode == "auto-split":
        session.preferences = {**(session.preferences or {}), "auto_split": True}
    planned(qapp, window)
    before_edit = deepcopy(session.blocks)
    essay = next(b for b in session.blocks if b.get("assignment_id") == "essay")
    session.blocks = [{**b, "start": None} if b is essay else b for b in session.blocks]
    if mode == "queued-save":
        session.save()
        before_replan = deepcopy(session.blocks)
        session.solve(everything=True)
    else:
        session.save()
        settled(qapp, window)
        before_replan = deepcopy(session.blocks)
        if mode == "joined-save":
            session.solve(everything=True, join=True)
        else:
            window.plan_review.replan_requested.emit()
    wait_until(
        qapp,
        lambda: not session.planning
        and not session.busy
        and not session.dirty
        and window.toast.text().startswith("Placed")
        and window.toast.button.isVisible(),
        timeout=20,
    )
    settled(qapp, window)
    assert window.toast.button.accessibleName() == "Undo"
    window.toast.button.click()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, window)
    assert session.blocks == (before_edit if mode == "joined-save" else before_replan)


@pytest.mark.parametrize("motion", ["reduce", "off"])
def test_undo_countdown_keeps_its_accessible_name_and_decreases(qapp, window, motion) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "motion": motion}
    window._apply_appearance()
    planned(qapp, window)
    initial = re.fullmatch(r"Undo · (\d+) s", window.toast.button.text())
    assert initial
    assert window.toast.button.accessibleName() == "Undo"
    assert not window.toast._progress.isVisible()
    QTest.qWait(1200)
    remaining = re.fullmatch(r"Undo · (\d+) s", window.toast.button.text())
    assert remaining and int(remaining.group(1)) < int(initial.group(1))


def test_undo_button_keeps_its_width_as_the_seconds_tick(qapp, window) -> None:
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", lambda: None)
    for _ in range(5):
        qapp.processEvents()
    button = window.toast.button
    first = button.width()
    words = window.toast.label.width()
    # Each count the toast shows after the first, down to the last second: none may change the room.
    for left_ms in (11000, 9500, 4200, 999):
        window.toast._timer.stop()
        window.toast._timer.start(left_ms)
        window.toast._sync_button_text()
        # Placed again, as the card's move or resize does, from what the button now asks for.
        window.toast._place_button()
        qapp.processEvents()
        assert re.fullmatch(r"Undo · \d+ s", button.text())
        assert button.width() == first
        assert window.toast.label.width() == words
