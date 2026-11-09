"""The More menu explains itself: every action says what it does, a greyed Unfinished says why and opens
nothing, Unfinished opens its list in every design, and Help, About and Sign out sit where they belong.

Its actions had no hover descriptions, a greyed "Unfinished" gave no reason, and "Unfinished" did
nothing at all in every design but Today's app. There was no Help and no About.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QPushButton,
    QToolTip,
    QWidgetAction,
)

from backend.tests.fake_clock import CLOCK, FakeClock
from desktop.native import settings
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.tokens import type_pt
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp, settled  # noqa: F401

# The row says it too ("Unfinished  None left"), so the reason and the toast are the same two words.
NOTHING_UNFINISHED = "None left"
ADDING = {
    "Add homework…": (
        "Add an assignment with its due date and how long it will take. FlexWeek finds time for it."
    ),
    "Add fixed time…": (
        "Add something that happens at a set time, like practice or a lesson. Homework is planned around it."
    ),
    "School hours…": "Set the days and times you're at school, so nothing is planned then.",
}
TOOLTIPS = {
    "Week as a list": "Every block this week, day by day, in time order. Ctrl+Shift+L",
    "Running late": (
        "Behind today? Say how late you are, and FlexWeek moves the rest of today's homework later."
    ),
    "Unfinished": NOTHING_UNFINISHED,
    "Routines": "Save this week's fixed times as a routine, or add a saved routine to a week.",
    "Quick focus": (
        "Open the focus timer, ready to start 30 minutes without picking homework. "
        "Change its length in Settings > Focus."
    ),
    "Replan all my homework": (
        "Find new times for all of this week's homework, as if none had a time yet. Homework you placed "
        "yourself stays put. Use it when your week has changed a lot."
    ),
    "Help": "What each screen is for, and the keyboard shortcuts.",
    "About FlexWeek": "The version, and where your plans are saved.",
    "Back to Material": "Switch back to the Material 3 style. Your week and homework stay the same.",
    "Sign out": "Sign out on this computer. Your plans stay saved in your account.",
    "Undo": "Nothing to undo yet.",
    "Redo": "Nothing to redo.",
    "Copy": "Copy the selected block to paste into another day. Ctrl+C",
    "Paste into (the selected day)": "Copy a block or a day first.",
    "Duplicate": "Make a copy of the selected block, with a preview first. Ctrl+D",
    "Copy (the selected day)": "Copy every block on the selected day to paste into another day.",
    "Copies of this week…": (
        "Save a copy of this week, or go back to an earlier one. FlexWeek keeps a restore point "
        "before big changes."
    ),
    "Reload this week": (
        "Load this week again as it's saved. Use it if something looks out of date."
    ),
}
PLAN = (
    "Find a time for homework that has none, around your fixed times and before it's due. Homework "
    "that already has a time keeps it."
)
SUGGEST = "Give homework without a time a suggested time. Drag any of them somewhere else if you like."


def actions(menu: QMenu) -> list[QAction]:
    """What a student can hover: every item with words, submenus opened, headings left out."""
    found = []
    for action in menu.actions():
        if action.isSeparator() or not action.text():
            continue
        if action.menu() is not None:
            found += actions(action.menu())
            continue
        found.append(action)
    return found


def opened_more(window: NativeWindow) -> QMenu:
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    return menu


def test_neither_menu_offers_save_and_ctrl_s_still_flushes(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    labels = [named(action.text()) for action in actions(opened_more(window))]
    assert "Save this week now" not in labels
    assert "Save" not in labels
    heard: list[bool] = []
    original = window.session.save

    def save() -> None:
        heard.append(True)
        original()

    window.session.save = save  # type: ignore[method-assign]
    try:
        window.session.dirty = True
        QTest.keyClick(window.week_table, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
        settled(qapp, window)
        assert heard == [True]
    finally:
        window.session.save = original  # type: ignore[method-assign]


def test_every_action_under_more_and_advanced_says_what_it_does(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    menu = opened_more(window)
    advanced = next(action.menu() for action in menu.actions() if action.menu() is not None)
    assert menu.toolTipsVisible() and advanced.toolTipsVisible()
    said = {named(action.text()): action.toolTip() for action in actions(menu) if action.isVisible()}
    assert said == TOOLTIPS


def test_the_add_menu_says_what_each_way_to_add_does(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """Adding left More for the Add button's menu, and its descriptions came with it."""
    menu = window.add_menu
    assert menu.toolTipsVisible()
    said = {action.text(): action.toolTip() for action in menu.actions() if action.text() in ADDING}
    assert said == ADDING
    assert window.findChild(QPushButton, "addButton").toolTip() == ADDING["Add homework…"]


def named(text: str) -> str:
    """Copy day and Paste name the selected day, which is today. What follows a tab is a note on the
    row, as Unfinished's reason, not its name."""
    text = text.partition("\t")[0]
    for verb in ("Copy ", "Paste into "):
        if text.startswith(verb):
            return verb + "(the selected day)"
    return text


def test_the_plan_button_and_the_plan_review_say_what_they_do(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    assert window.solve_button.toolTip() == PLAN
    window.session.preferences = {**window.session.preferences, "planning_style": "manual"}
    window._sync_chrome()
    assert window.solve_button.text() == "Suggest times"
    assert window.solve_button.toolTip() == SUGGEST
    assert window.findChild(QPushButton, "planReviewDismiss").toolTip() == "Hide this list."
    assert window.findChild(QPushButton, "planReviewReplan").toolTip() == TOOLTIPS["Replan all my homework"]


def unfinished_action(window: NativeWindow) -> QAction:
    return next(action for action in actions(opened_more(window)) if named(action.text()) == "Unfinished")


def test_unfinished_with_nothing_unfinished_is_greyed_and_says_why(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    window.session.save()
    settled(qapp, window)
    action = unfinished_action(window)
    assert action.isEnabled() is False
    assert action.toolTip() == NOTHING_UNFINISHED
    # On the row itself too, for anyone who does not wait for a tooltip (T23 of the 0.17.0 audit).
    assert action.text() == "Unfinished\tNone left"
    window._show_unfinished()
    assert window.toast.text() == NOTHING_UNFINISHED
    assert not window.unfinished_panel.isVisibleTo(window)


def test_unfinished_opens_its_list_in_any_design(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """Homework from last week with two hours still to plan, seen from the week after, in Timeline."""
    session = window.session
    week = date.fromisoformat(session.week_start)
    session.add_block({"id": "school", "title": "School", "kind": "locked", "start": "08:00",
                       "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    session.add_homework({"id": "essay", "title": "History essay", "estimate_min": 120, "revision": 0,
                          "due": (CLOCK.today() - timedelta(days=3)).isoformat() + "T12:00"})
    session.save()
    settled(qapp, window)
    planned = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.delete_block(planned["id"])
    session.save()
    settled(qapp, window)
    later = (week + timedelta(days=7)).isoformat()
    session.load_week(later)
    wait_until(qapp, lambda: session.week_start == later and not session.busy)
    window.unfinished_panel.hide()
    window._layout = sanitize_layout({"main": "timeline", "day": "one"})
    window._on_week()
    qapp.processEvents()
    action = unfinished_action(window)
    assert action.isEnabled()
    action.trigger()
    qapp.processEvents()
    panel = window.unfinished_panel
    assert panel.isVisibleTo(window), "Timeline showed nothing"
    rows = [label.text() for label in panel.findChildren(QLabel) if label.isVisibleTo(window)]
    due = CLOCK.today() - timedelta(days=3)
    assert f"History essay · 2 h left · due {due:%a} {due.day} {due:%b} · Overdue" in rows
    assert action.toolTip() == (
        "Overdue and earlier-week homework that still needs time. Plan it into this week."
    )


def assert_count_on_plan_not_on_more(window: NativeWindow) -> None:
    """The 1.0.0 week bar counts homework that needs a time on Plan's pill; More carries no count."""
    assert window.more_button.accessibleName() == "More"
    assert window.solve_button.accessibleName().endswith(", 1 homework still needs time")


def test_unfinished_stays_open_when_the_week_changes_after_it_is_opened(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """Opened from More, the list stayed open only until the next change to the week: a save or a
    reload arriving a moment later folded it back into its badge. It stays open until closed."""
    session = window.session
    week = date.fromisoformat(session.week_start)
    session.add_homework({"id": "essay", "title": "History essay", "estimate_min": 120, "revision": 0,
                          "due": (CLOCK.today() - timedelta(days=3)).isoformat() + "T12:00"})
    session.save()
    settled(qapp, window)
    planned = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.delete_block(planned["id"])
    session.save()
    settled(qapp, window)
    later = (week + timedelta(days=7)).isoformat()
    session.load_week(later)
    wait_until(qapp, lambda: session.week_start == later and not session.busy)
    window._on_week()
    window.unfinished_panel.hide()
    unfinished_action(window).trigger()
    qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window)
    window._on_week()
    qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window), "a change to the week closed the list"
    assert_count_on_plan_not_on_more(window)


def test_more_badge_counts_open_homework_before_an_earlier_week_prompt(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    session = window.session
    due = (date.fromisoformat(session.week_start) + timedelta(days=9)).isoformat() + "T23:59"
    session.add_homework(
        {
            "id": "history",
            "title": "History",
            "estimate_min": 120,
            "revision": 0,
            "due": due,
        }
    )
    session.save()
    settled(qapp, window)
    window._unfinished_introduced = False
    window._on_week()
    assert len(session.homework_time_needed()) == 1
    assert_count_on_plan_not_on_more(window)


def test_more_badge_counts_work_due_this_week_that_the_rail_already_lists(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """Work due this week with a chip in Not placed yet is counted there and on More: the count is a pill
    on More's corner, so it never moves the week (0.19.2, P1 rule d)."""
    session = window.session
    due = (date.fromisoformat(session.week_start) + timedelta(days=6)).isoformat() + "T23:59"
    session.add_homework(
        {"id": "math", "title": "Math", "estimate_min": 60, "revision": 0, "due": due}
    )
    session.save()
    settled(qapp, window)
    window._unfinished_introduced = False
    window._on_week()
    assert [item["assignment_id"] for item in session.homework_time_needed()] == ["math"]
    assert_count_on_plan_not_on_more(window)
    assert window.rail.waiting_count.text() == "1"


def test_unfinished_is_on_for_work_that_is_not_yet_overdue(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
) -> None:
    """#14 asked the button to follow the overdue-only list. 0.19.2 (P1 rule d) made the count the one the
    rail shows: work still needing time is listed and counted whether or not it is overdue."""
    week = date.fromisoformat(window.session.week_start)
    # Saturday evening of the open week while the essay is planned; Monday morning of the next week
    # once it is open. The essay is due that Tuesday, so it is not overdue, but it is left from a week
    # that was saved before the clock's week.
    saturday = datetime.combine(week + timedelta(days=5), datetime.min.time()).replace(hour=18)
    monday = datetime.combine(week + timedelta(days=7), datetime.min.time()).replace(hour=9)
    clock.set(saturday)
    session = window.session
    session.add_block({"id": "school", "title": "School", "kind": "locked", "start": "08:00",
                       "duration_min": 390, "days": [0, 1, 2, 3, 4]})
    session.add_homework({"id": "essay", "title": "History essay", "estimate_min": 120, "revision": 0,
                          "due": (week + timedelta(days=8)).isoformat() + "T15:30"})
    session.save()
    settled(qapp, window)
    assert any(block.get("assignment_id") == "essay" for block in session.blocks)
    later = (week + timedelta(days=7)).isoformat()
    session.load_week(later)
    wait_until(qapp, lambda: session.week_start == later and not session.busy)
    clock.set(monday)
    assert session.unfinished()
    action = unfinished_action(window)
    button = window.findChild(QPushButton, "unfinishedOpen")
    assert action.isEnabled() is True
    assert action.text() == "Unfinished\t1 left"
    assert button is not None and button.isEnabled() is True
    window._show_unfinished()
    assert window.unfinished_panel.isVisibleTo(window) and window.unfinished_panel.list.count() == 1


def test_a_description_is_as_large_as_the_text_the_student_chose(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """At Large the descriptions stayed at the system's small tooltip size."""
    for text in ("normal", "large"):
        knobs = {**window._look.get("knobs", {}), "text": text}
        window._look = sanitize_look({**window._look, "knobs": knobs})
        window._apply_appearance()
        button = window.solve_button
        QToolTip.showText(button.mapToGlobal(QPoint(0, button.height())), button.toolTip(), button)
        qapp.processEvents()
        tip = next(w for w in qapp.topLevelWidgets() if w.objectName() == "qtooltip_label" and w.isVisible())
        assert tip.font().pointSizeF() == type_pt("body", text), text
        # Gone at once, as Qt does when a tip times out: hideText() only hides after a moment, and the
        # same words on the same button again are then taken as the tip already showing, which hides.
        tip.close()
        tip.deleteLater()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_help_and_about_are_under_more(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(settings.HelpDialog, "exec", lambda dialog: opened.append(dialog.windowTitle()) or 0)
    monkeypatch.setattr(settings.AboutDialog, "exec", lambda dialog: opened.append(dialog.windowTitle()) or 0)
    for action in actions(opened_more(window)):
        if action.text() in {"Help", "About FlexWeek"}:
            action.trigger()
    assert opened == ["Help", "About FlexWeek"]


def test_every_row_under_more_has_an_icon_and_log_out_stands_apart(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """Decision 22: icons on the More menu, "Advanced" named for what it holds, and Sign out after a
    line of its own, never with Help and About."""
    from desktop.native.menus import ICON, Menu

    menu = opened_more(window)
    assert isinstance(menu, Menu)
    named = [action for action in menu.actions() if action.text()]
    assert all(action.property(ICON) for action in named), [a.text() for a in named if not a.property(ICON)]
    edits = next(action for action in named if action.menu() is not None)
    assert edits.text() == "Undo, copy and save"
    assert [action.text() for action in edits.menu().actions()][:2] == ["Undo", "Redo"]
    assert all(action.property(ICON) for action in edits.menu().actions())
    rows = [
        action.text() or "---"
        for action in menu.actions()
        if action.isVisible() and not action.menu() and not isinstance(action, QWidgetAction)
    ]
    assert rows[-5:] == ["---", "Help", "About FlexWeek", "---", "Sign out"]
    assert all(action.property(ICON) for action in window.add_menu.actions()[:3]), "the Add menu's three"


def test_more_undo_is_enabled_when_the_toast_offers_undo(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window._set_notice("Planned 1 homework block.", "Undo", lambda: None)
    qapp.processEvents()
    monkeypatch.setattr(window.session, "can_undo", lambda: False)
    menu = opened_more(window)
    undo = next(action for action in actions(menu) if action.text() == "Undo")
    assert undo.isEnabled()
    window.toast.hide()
    qapp.processEvents()
    menu = opened_more(window)
    undo = next(action for action in actions(menu) if action.text() == "Undo")
    assert not undo.isEnabled()
