"""Material's one-letter keys: 1 to 5 switch views under their own Settings switch (on), and P, Z and F plan,
undo and open Focus under another (off until a student turns it on). Ctrl+Z and the zoom keys answer to
neither. Expected values come from the decision, not from what the QML does."""

# ruff: noqa: F811
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.tests.waiting import wait_until
from desktop.tests.week.support_material import (
    _bridge,
    _homework,
    _look,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import look_file, qapp, settled  # noqa: F401

CTRL = Qt.KeyboardModifier.ControlModifier


def _press(window, key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
    QTest.keyClick(window._material_page._quick, key, modifiers)
    _pump(QApplication.instance())


def _waiting(window, qapp, key: str, title: str) -> None:
    """One homework card with no time yet."""
    due = (_week_monday(window) + timedelta(days=6)).isoformat()
    _homework(window, key, title, 30, due)
    settled(qapp, window)
    _pump(qapp)


def _placed(window, key: str) -> bool:
    return bool(next(b for b in window.session.blocks if b.get("assignment_id") == key).get("start"))


def _place_by_button(window, qapp, key: str) -> None:
    _bridge(window).week.planOne(key)
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    _pump(qapp)
    assert _placed(window, key)


def test_by_default_the_number_keys_switch_views_and_the_letter_keys_do_nothing(qapp, window) -> None:
    root = _reset(window, qapp)
    bridge = _bridge(window)
    assert bridge.property("shortcuts") is True
    for key, screen in (
        (Qt.Key.Key_1, "day"),
        (Qt.Key.Key_3, "month"),
        (Qt.Key.Key_4, "myday"),
        (Qt.Key.Key_2, "week"),
    ):
        _press(window, key)
        assert bridge.property("screen") == screen, key

    _waiting(window, qapp, "sheet", "Math worksheet")
    _press(window, Qt.Key.Key_P)
    _pump(qapp, 40)
    assert not window.session.busy
    assert not _placed(window, "sheet"), "P did not plan"
    assert _qml(root, "homeworkCount").property("text") == "1"

    _waiting(window, qapp, "poster", "Science poster")
    _place_by_button(window, qapp, "poster")
    _press(window, Qt.Key.Key_Z)
    _pump(qapp, 40)
    assert not window.session.can_redo(), "Z did not undo"
    assert _placed(window, "poster")

    _press(window, Qt.Key.Key_F)
    assert not bridge.focus.open, "F did not open Focus"
    assert bridge.property("letterKeys") is False


def test_with_the_letter_keys_on_p_plans_z_undoes_and_f_opens_focus(qapp, window) -> None:
    root = _reset(window, qapp)
    bridge = _bridge(window)
    _look(window, letters=True)
    assert bridge.property("letterKeys") is True
    _waiting(window, qapp, "sheet", "Math worksheet")
    _press(window, Qt.Key.Key_P)
    wait_until(qapp, lambda: _snack(window).startswith("Placed") and not window.session.busy)
    assert _placed(window, "sheet"), "P planned"
    _press(window, Qt.Key.Key_Z)
    wait_until(qapp, lambda: not window.session.busy and window.session.can_redo())
    assert not _placed(window, "sheet"), "Z undid the plan"
    assert _qml(root, "homeworkCount").property("text") == "1"
    _press(window, Qt.Key.Key_F)
    assert bridge.focus.open, "F opened Focus"


def test_with_the_number_switch_off_the_number_keys_do_nothing_and_the_letter_keys_still_answer_to_theirs(
    qapp, window
) -> None:
    _reset(window, qapp)
    bridge = _bridge(window)
    _look(window, shortcuts=False, letters=True)
    assert bridge.property("shortcuts") is False
    assert bridge.property("letterKeys") is True
    for key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5):
        _press(window, key)
        assert bridge.property("screen") == "week", key
    _press(window, Qt.Key.Key_F)
    assert bridge.focus.open, "the letter switch is its own"


def test_ctrl_z_still_undoes_with_both_switches_off(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, shortcuts=False, letters=False)
    assert _bridge(window).property("letterKeys") is False
    _waiting(window, qapp, "sheet", "Math worksheet")
    _place_by_button(window, qapp, "sheet")
    _press(window, Qt.Key.Key_Z, CTRL)
    wait_until(qapp, lambda: not window.session.busy and window.session.can_redo())
    assert not _placed(window, "sheet")


def test_an_old_look_file_that_had_the_one_switch_on_leaves_the_letter_keys_off(qapp, window) -> None:
    _reset(window, qapp)
    look_file().write_text(json.dumps({"material": {"shortcuts": True}}))
    window._material_page.publish()
    _pump(qapp)
    bridge = _bridge(window)
    assert bridge.property("shortcuts") is True
    assert bridge.property("letterKeys") is False
    _press(window, Qt.Key.Key_F)
    assert not bridge.focus.open


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (None, False),
        ({}, False),
        ({"material": {}}, False),
        ({"material": {"shortcuts": True}}, False),
        ({"material": {"letters": "yes"}}, False),
        ({"material": {"letters": True}}, True),
        ({"material": {"letters": False, "shortcuts": True}}, False),
    ],
)
def test_the_letter_keys_are_on_only_when_the_look_file_says_true(stored, expected) -> None:
    from desktop.native.material.theme import read_letter_keys

    assert read_letter_keys(stored) is expected


SHIFT = Qt.KeyboardModifier.ShiftModifier


def _screen(window) -> str:
    return str(_bridge(window).property("screen"))


def test_with_the_letter_keys_on_d_w_and_m_open_day_week_and_month(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    for key, screen in ((Qt.Key.Key_D, "day"), (Qt.Key.Key_M, "month"), (Qt.Key.Key_W, "week")):
        _press(window, key)
        assert _screen(window) == screen, key


def test_with_the_letter_keys_on_j_and_k_step_the_week_the_day_and_the_month(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    session = window.session
    bridge = _bridge(window)
    week = _week_monday(window)
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.week_start == (week + timedelta(days=7)).isoformat())
    _press(window, Qt.Key.Key_K)
    wait_until(qapp, lambda: session.week_start == week.isoformat())

    _press(window, Qt.Key.Key_D)
    shown = str(bridge.day.property("iso"))
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: bridge.day.property("iso") != shown)
    following = date.fromisoformat(shown) + timedelta(days=1)
    assert bridge.day.property("iso") == following.isoformat()
    _press(window, Qt.Key.Key_K)
    wait_until(qapp, lambda: bridge.day.property("iso") == shown)

    _press(window, Qt.Key.Key_M)
    month = session.selected_month
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.selected_month != month)
    _press(window, Qt.Key.Key_K)
    wait_until(qapp, lambda: session.selected_month == month)


def test_with_the_letter_keys_on_t_comes_back_to_today(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    session = window.session
    home = session.week_start
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.week_start != home)
    _press(window, Qt.Key.Key_T)
    wait_until(qapp, lambda: session.week_start == home)
    assert _screen(window) == "week"
    _press(window, Qt.Key.Key_4)
    assert _screen(window) == "myday"
    _press(window, Qt.Key.Key_T)
    assert _screen(window) == "day", "from My day T opens Day, which opens on today"


def test_with_the_letter_keys_on_t_on_day_shows_today_again(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    bridge = _bridge(window)
    _press(window, Qt.Key.Key_D)
    today = str(bridge.day.property("iso"))
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: bridge.day.property("iso") != today)
    _press(window, Qt.Key.Key_T)
    wait_until(qapp, lambda: bridge.day.property("iso") == today)
    assert _screen(window) == "day"


def test_with_the_letter_keys_on_t_on_month_shows_this_month_again(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    session = window.session
    _press(window, Qt.Key.Key_M)
    wait_until(qapp, lambda: bool(session.selected_month))
    this_month = date.fromisoformat(session.today_iso()).strftime("%Y-%m")
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.selected_month != this_month)
    _press(window, Qt.Key.Key_T)
    wait_until(qapp, lambda: session.selected_month == this_month)
    assert _screen(window) == "month", "T on Month stays on Month"


def test_with_the_letter_keys_on_c_opens_add_homework(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    sheets = _bridge(window).sheets
    assert sheets.property("kind") == ""
    _press(window, Qt.Key.Key_C)
    assert sheets.property("kind") == "homework"


def test_with_the_letter_keys_off_none_of_the_new_letters_does_anything(qapp, window) -> None:
    _reset(window, qapp)
    session = window.session
    home = session.week_start
    for key in (Qt.Key.Key_D, Qt.Key.Key_M, Qt.Key.Key_J, Qt.Key.Key_K, Qt.Key.Key_T, Qt.Key.Key_C):
        _press(window, key)
        assert _screen(window) == "week", key
        assert _bridge(window).sheets.property("kind") == "", key
        assert session.week_start == home, key


def test_a_letter_with_shift_or_ctrl_is_not_one_of_the_letter_keys(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    session = window.session
    home = session.week_start
    for key in (Qt.Key.Key_D, Qt.Key.Key_M, Qt.Key.Key_J, Qt.Key.Key_C, Qt.Key.Key_F, Qt.Key.Key_P):
        for modifiers in (SHIFT, CTRL):
            _press(window, key, modifiers)
            assert _screen(window) == "week", (key, modifiers)
            assert _bridge(window).sheets.property("kind") == "", (key, modifiers)
            assert not _bridge(window).focus.open, (key, modifiers)
    assert session.week_start == home


def test_the_letter_keys_wait_while_a_sheet_is_open(qapp, window) -> None:
    _reset(window, qapp)
    _look(window, letters=True)
    bridge = _bridge(window)
    _press(window, Qt.Key.Key_C)
    assert bridge.sheets.property("kind") == "homework"
    for key in (Qt.Key.Key_D, Qt.Key.Key_M, Qt.Key.Key_J, Qt.Key.Key_T):
        _press(window, key)
        assert _screen(window) == "week", key
    assert bridge.sheets.property("kind") == "homework"


@pytest.mark.parametrize("letters", [False, True])
def test_ctrl_shift_f_starts_quick_focus_whatever_the_switches_say(qapp, window, letters) -> None:
    _reset(window, qapp)
    _look(window, letters=letters)
    bridge = _bridge(window)
    assert not bridge.focus.open
    _press(window, Qt.Key.Key_F, CTRL)
    assert not bridge.focus.open, "Ctrl+F does nothing for now"
    _press(window, Qt.Key.Key_F, CTRL | SHIFT)
    assert bridge.focus.open, "Ctrl+Shift+F opened Quick focus"
    assert window.session.focus is None, "it is ready to start, as the Quick focus row is"


def test_ctrl_shift_f_does_nothing_while_a_sheet_is_open(qapp, window) -> None:
    _reset(window, qapp)
    bridge = _bridge(window)
    bridge.addHomework()
    _pump(qapp)
    assert bridge.sheets.property("kind") == "homework"
    _press(window, Qt.Key.Key_F, CTRL | SHIFT)
    assert not bridge.focus.open
