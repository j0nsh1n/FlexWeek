"""The rail beside the week: a running timer is one line in it, and when the window is too narrow it
folds, listing the homework that has no time yet as a chip the student can drag."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import sys

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.layouts.base import NARROW_WIDTH
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_weekview import (  # noqa: F401
    WAITING_WORDS,
    add_waiting_poster,
    essay_week,
    pump,
    send_mouse,
    set_text_size,
)
from desktop.tests.window_support import free, qapp  # noqa: F401


def fold_week(qapp: QApplication, window: NativeWindow, width: int = 800, height: int = 860) -> None:
    window.resize(width, height)
    pump(qapp)
    assert not window.rail.folded


def shown_chip_names(window: NativeWindow) -> list[str]:
    return [chip.accessibleName() for chip in window.rail.chips() if chip.isVisible()]


def test_a_running_timer_in_todays_app_is_one_line_in_the_rail(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    window = essay_week
    essay = next(b for b in window.session.blocks if b.get("assignment_id") == "math")
    window.session.start_focus(essay["id"], 2)
    wait_until(qapp, lambda: window.session.focus is not None)
    window._on_week()
    qapp.processEvents()
    panel = window.focus_panel
    assert panel.isVisible() and window.rail.isAncestorOf(panel)
    assert panel.task.isVisible()
    assert not panel.phase.isVisible() and not panel.time.isVisible()
    line = panel.task.text()
    title = window.session.focus.get("title") or ""
    assert title and line.startswith(f"{title} · ") and " left" in line
    assert [b.text() for b in panel.findChildren(QPushButton) if b.isVisible()] == ["Focus screen"]


def test_the_folded_rail_shows_a_waiting_chip_not_a_bare_line(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    window = essay_week
    add_waiting_poster(qapp, window)
    window.resize(NARROW_WIDTH - 1, 860)
    pump(qapp)
    rail = window.rail
    assert not rail.folded
    assert rail.waiting_label.text() == WAITING_WORDS
    assert shown_chip_names(window) == ["Poster · 30 min"]


def test_the_folded_waiting_chip_opens_a_row_under_the_line(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    window = essay_week
    add_waiting_poster(qapp, window)
    fold_week(qapp, window, NARROW_WIDTH - 1)
    rail = window.rail
    assert rail.waiting_label.text() == WAITING_WORDS
    waiting = next(
        widget
        for widget in rail.chips()
        if widget.property("block_id") and widget.property("tray") and widget.isVisible()
    )
    assert waiting.shown_title() == "Poster"
    assert waiting.accessibleName() == "Poster · 30 min"
    window.resize(1280, 860)
    pump(qapp)
    assert not rail.folded
    fold_week(qapp, window, NARROW_WIDTH - 1)
    # Closing the window while the row is open raises nothing, in a slot or while a widget is freed.
    caught: list[BaseException] = []
    previous_hook = sys.excepthook
    previous_unraisable = sys.unraisablehook

    def hook(kind, value, traceback) -> None:
        caught.append(value)
        previous_hook(kind, value, traceback)

    def unraisable(args) -> None:
        if args.exc_value is not None:
            caught.append(args.exc_value)
        previous_unraisable(args)

    sys.excepthook = hook
    sys.unraisablehook = unraisable
    try:
        window.close()
        free(window)
    finally:
        sys.excepthook = previous_hook
        sys.unraisablehook = previous_unraisable
    assert caught == []


def test_the_folded_waiting_chip_keeps_its_words_at_800_in_both_text_sizes(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    window = essay_week
    add_waiting_poster(qapp, window)
    for size in ("normal", "large"):
        set_text_size(window, size)
        fold_week(qapp, window, 800)
        assert window.rail.waiting_label.text() == WAITING_WORDS
        assert shown_chip_names(window) == ["Poster · 30 min"]


def test_a_drag_from_the_folded_waiting_row_starts(
    qapp: QApplication,
    essay_week: NativeWindow,
) -> None:
    window = essay_week
    waiting = add_waiting_poster(qapp, window)
    window.move(0, 0)
    fold_week(qapp, window, 800, 720)
    chip = next(
        widget
        for widget in window.findChildren(QPushButton)
        if widget.property("block_id") == waiting["id"] and widget.property("tray") and widget.isVisible()
    )
    hours = window.week_table.hours
    if not hours.tracks:
        hours.resize(980, 640)
        hours.relayout()
    hours.reveal(4, 15 * 60, 18 * 60)
    qapp.processEvents()
    start = chip.mapToGlobal(chip.rect().center())
    end = hours.point_for(4, 16 * 60)
    send_mouse(chip, QEvent.Type.MouseButtonPress, start, True)
    for step in range(1, 9):
        moved = QPoint(
            start.x() + (end.x() - start.x()) * step // 8,
            start.y() + (end.y() - start.y()) * step // 8,
        )
        send_mouse(hours, QEvent.Type.MouseMove, moved, True)
        if window.hand.active:
            break
    qapp.processEvents()
    assert window.hand.active
    window.hand.cancel()
