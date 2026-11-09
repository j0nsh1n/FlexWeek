"""The Material week's weekend toggle and its saves, a week load that fails, and the timers the
week's bridge owns."""

# ruff: noqa: F811
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication

from desktop.native import material as material_package
from desktop.native.material.bridge_week import WeekBridge
from desktop.tests.week.support_material import (
    _bridge,
    _click,
    _named,
    _pump,
    _qml,
    _reset,
    _snack,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_clicking_toggle_weekends_swaps_between_seven_and_five_columns(qapp, window) -> None:
    root = _reset(window, qapp)
    toggle = _qml(root, "toggleWeekends")
    assert len(_named(root, "dayHeader")) == 7
    _click(window, toggle)
    settled(qapp, window)
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 5
    _click(window, toggle)
    settled(qapp, window)
    _pump(qapp)
    assert len(_named(root, "dayHeader")) == 7


def test_the_weekend_choice_survives_a_preferences_refresh_and_a_failed_save_restores_it(
    qapp, window
) -> None:
    root = _reset(window, qapp)
    session = window.session
    _click(window, _qml(root, "toggleWeekends"))
    settled(qapp, window)
    assert session.preferences["show_weekends"] is False
    session._fetch_preferences()
    settled(qapp, window)
    _pump(qapp)
    assert session.preferences["show_weekends"] is False
    assert len(_named(root, "dayHeader")) == 5

    def refuse(_updates: dict, then) -> bool:
        then(False)
        return True

    session.save_preferences = refuse
    _click(window, _qml(root, "toggleWeekends"))
    _pump(qapp)
    assert session.preferences["show_weekends"] is False
    assert len(_named(root, "dayHeader")) == 5
    assert _snack(window) == "Couldn't save the weekend setting. Try again."
    snackbar = _qml(root, "materialSnackbar")
    assert snackbar.property("actionText") == ""
    assert snackbar.property("activeFocusOnTab") is False
    undo_calls = []
    session.undo = lambda: undo_calls.append(True)
    snackbar.actionClicked.emit()
    _pump(qapp)
    assert undo_calls == [], "A failed preference save cannot undo a schedule change"


def test_a_failed_week_load_is_not_retried_and_an_account_change_cancels_a_pending_one(qapp, window) -> None:
    _reset(window, qapp)
    session = window.session
    home = session.week_start
    target = (date.fromisoformat(home) + timedelta(days=7)).isoformat()
    calls = []

    def fail(start=None, **_kwargs) -> None:
        calls.append(start)
        session.busy = True
        session.busy_changed.emit(True)

    session.load_week = fail
    week = _bridge(window).property("week")
    week.next()
    session.busy = False
    session.busy_changed.emit(False)
    session.week_changed.emit()
    _pump(qapp, 12)
    assert calls == [target]
    assert session.week_start == home

    week.next()
    week.next()
    session.busy = False
    session.busy_changed.emit(False)
    session.week_changed.emit()
    _pump(qapp, 12)
    later = (date.fromisoformat(home) + timedelta(days=14)).isoformat()
    assert calls == [target, target, later]

    week.next()
    session.account_changed.emit(None)
    session.busy = False
    session.busy_changed.emit(False)
    _pump(qapp, 12)
    assert calls == [target, target, later]


def test_a_zero_timer_dies_with_its_bridge(qapp) -> None:
    """The 0 ms target timer is owned by the bridge, so a bridge dropped in the same turn takes it
    with it instead of running the slot from behind a deleted wrapper."""
    fired: list[str] = []
    session = SimpleNamespace(busy=False, week_start="2026-11-02", load_week=fired.append)
    holder = QObject()
    bridge = WeekBridge(SimpleNamespace(session=session), holder)
    # A plain recording stand-in, so the call itself proves the timer fired; the real slot would
    # only raise on the deleted C++ object before it reached the session.
    bridge._flush_target = lambda: fired.append("flush")
    bridge._target_week = "2026-11-09"
    bridge._settle_navigation()
    bridge.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert fired == []


def test_every_zero_timer_in_material_has_an_owner() -> None:
    """A singleShot(0, ...) without a context object outlives the bridge that made it and runs its slot
    on a deleted wrapper. Day's ensure_today is the pattern the rest of material/ follows."""
    folder = Path(material_package.__file__).resolve().parent
    found = 0
    for path in sorted(folder.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "singleShot" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value == 0:
                found += 1
                assert len(node.args) >= 3, f"{path.name}:{node.lineno} singleShot without an owner"
    assert found >= 4, "the zero timers this rule exists for are gone; drop the rule with them"
