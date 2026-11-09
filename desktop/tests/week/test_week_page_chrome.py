# ruff: noqa: F811
"""The week page around its hours: Today, the title, the keys that act, the clipboard line, the top bar
while the session is busy, and when the window is dressed again."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from backend import clock as wall_clock  # noqa: E402
from desktop.native.calendar import monday_of  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)


def test_today_jumps_the_planner_to_this_week(qapp: QApplication, window: NativeWindow) -> None:
    click(window, "nextWeek")
    settled(qapp, window)
    assert window.session.week_start != monday_of(wall_clock.today().isoformat())
    click(window, "todayWeek")
    settled(qapp, window)
    assert window.session.week_start == monday_of(wall_clock.today().isoformat())


def test_a_week_across_two_months_shortens_to_month_abbreviations_not_an_ellipsis(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The short date stays the same when the controls wrap beneath it."""
    window.session.load_week("2026-09-28")
    wait_until(qapp, lambda: not window.session.busy and window.session.week_start == "2026-09-28")
    seen = {}
    for width in (1440, 1280, 1150, 1024):
        window.resize(width, 768)
        qapp.processEvents()
        seen[width] = window.week_title.text()
        assert window.week_title.accessibleName() == "28 Sep – 4 Oct", width
    assert set(seen.values()) == {"28 Sep – 4 Oct"}, seen


def test_advanced_shortcuts_still_act(qapp: QApplication, window: NativeWindow) -> None:
    before = len(window.session.blocks)
    QTest.keyClick(window.week_table, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    settled(qapp, window)
    assert len(window.session.blocks) != before or window.session.can_redo() is True
    window.session.select_block("school", 0)
    QTest.keyClick(window.week_table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert (window.session.clipboard or {}).get("kind") == "block"
    window.session.clipboard = None
    QTest.keyClick(window.week_table, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    # Ctrl+S is how Save is reached now that it lives under Advanced.
    window.session.dirty = True
    QTest.keyClick(window.week_table, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    settled(qapp, window)
    assert window.session.dirty is False or window.session.busy is True


def test_the_clipboard_line_only_appears_when_it_has_something_to_say(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._on_week()
    qapp.processEvents()
    assert window.clipboard_summary.isVisible() is False
    block = next(b for b in window.session.blocks if b.get("kind") == "locked")
    window.session.select_block(block["id"], 0)
    window.session.copy_selected()
    window._on_week()
    qapp.processEvents()
    assert window.clipboard_summary.isVisible() is True
    assert window.clipboard_summary.text().startswith("Copied: ")


def test_a_short_busy_spell_takes_no_clicks_but_does_not_grey_the_top_bar(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Plan my homework greyed the whole top bar for one frame. A plan takes a few milliseconds; the bar
    greys only once the session has been busy BUSY_LOOK_MS, and takes no click from the first moment."""
    session = window.session
    plan = window.findChild(QPushButton, "solveButton")
    pressed: list[bool] = []
    plan.clicked.connect(lambda: pressed.append(True))
    session.busy = True
    session.busy_changed.emit(True)
    assert plan.isEnabled(), "not greyed at once"
    QTest.mouseClick(plan, Qt.MouseButton.LeftButton)
    assert pressed == [], "but it takes no click while busy"
    session.busy = False
    session.busy_changed.emit(False)
    assert window._busy_look.isActive() is False, "the delay before greying is cancelled"
    assert plan.isEnabled(), "a short spell never greys it"
    session.busy = True
    session.busy_changed.emit(True)
    wait_until(qapp, lambda: not plan.isEnabled(), what="a long spell greying the bar")
    session.busy = False
    session.busy_changed.emit(False)
    assert plan.isEnabled(), "and it comes back at once"


def test_a_change_to_the_week_does_not_restyle_the_window_when_the_look_is_the_same(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every change to the week re-dressed the whole window, about 26 ms a time, for nothing."""
    dressed: list[str] = []
    original = window.setStyleSheet
    window._layout = sanitize_layout(
        {**window._layout, "options": {**window._layout["options"], "classic": {"look": "your"}}}
    )
    window._apply_appearance()
    monkeypatch.setattr(window, "setStyleSheet", lambda sheet: (dressed.append(sheet), original(sheet)))
    window._on_week()
    window._on_week()
    assert dressed == []
    window.session.preferences = {**window.session.preferences, "theme_pack": "dark-frost"}
    window._on_week()
    assert len(dressed) == 1, "a new look is still put on at once"
