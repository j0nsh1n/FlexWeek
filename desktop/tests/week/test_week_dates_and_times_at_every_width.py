"""The week's title, the Plan button and the times inside blocks keep saying the same thing as the window
narrows to its smallest size. How they fit is checked in pictures (week.plan-button-at-narrow-widths)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_typing import DESIGNS, hours, hours_window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.mark.parametrize("design", DESIGNS)
@pytest.mark.parametrize("preset", ["default", "paper"])
def test_the_week_title_uses_the_same_short_date_at_every_width(
    qapp: QApplication,
    hours_window: NativeWindow,
    design: str,
    preset: str,
) -> None:
    window = hours_window
    session = window.session
    session.load_week("2026-09-28")
    wait_until(qapp, lambda: not session.busy)
    window._layout = sanitize_layout({"main": design})
    window._look = sanitize_look({"preset": preset})
    window._apply_appearance()
    window._on_week()
    for width in (1280, 1000, 810):
        window.resize(width, 800)
        for _ in range(4):
            qapp.processEvents()
        assert window.week_title.text() == "28 Sep – 4 Oct"
        assert window.week_title.full_text() == "28 Sep – 4 Oct"
        if design == "retro":
            assert window._views["retro"]._windows["week"].bar.text() == "Week.exe - 28 Sep – 4 Oct"


def test_plan_says_a_whole_word_at_every_width_and_gives_the_words_back(
    qapp: QApplication, hours_window: NativeWindow
) -> None:
    """One order at every width, so a wrapped bar says "Plan"; a wide window gives the words back."""
    window = hours_window
    for width in (1280, 1000, 810, 1280):
        window.resize(width, 800)
        for _ in range(4):
            qapp.processEvents()
        assert window.solve_button.text() in ("Plan my homework", "Plan homework", "Plan")
    assert window.solve_button.text() == "Plan my homework", "1280 pixels has room for the words"


def test_narrow_week_blocks_still_include_their_times(
    qapp: QApplication, hours_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from desktop.native.hours import canvas
    from desktop.native.weekmodel import clock_label

    window = hours_window
    window.session.preferences = {**(window.session.preferences or {}), "clock_24h": True}
    window._layout = sanitize_layout({"main": "classic"})
    window._look = sanitize_look({"preset": "default"})
    window._apply_appearance()
    window._on_week()
    window.findChild(QAbstractButton, "viewWeek").click()
    written: list[str] = []
    original = canvas._paint_layout

    def record(painter, lay, *args, **kwargs) -> None:
        written.extend(line.text for line in lay)
        original(painter, lay, *args, **kwargs)

    monkeypatch.setattr(canvas, "_paint_layout", record)
    for width in (1280, 1000, 810):
        window.resize(width, 800)
        for _ in range(4):
            qapp.processEvents()
        assert window.width() == width
        scroll = hours(window)
        assert scroll.canvas is window.week_table.hours
        scroll.canvas.reveal(0, 480, 540)
        qapp.processEvents()
        written.clear()
        assert not scroll.canvas.grab().isNull()
        assert any(words.startswith(clock_label(480)) for words in written), (width, written)


def test_new_recovery_codes_are_listed_one_to_a_line(hours_window: NativeWindow) -> None:
    """The codes' page is gone once the week is open, and made again when new codes come. The face
    they are written in is checked in a picture (week.recovery-codes-in-mono)."""
    codes = [f"aaaa-bbbb-cccc-dd{n:02d}" for n in range(8)]
    hours_window.session.recovery_codes.emit(codes)
    assert hours_window.recovery_list.text().splitlines() == codes
