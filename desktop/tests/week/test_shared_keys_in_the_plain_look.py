"""The plain look's one-key shortcuts: 1 to 5 under Number keys (on), the letters under Letter keys (off),
the same two saved settings Material reads. Ctrl+Shift+F is Quick focus. Expected values come from the
decision (one Google-style set in both looks), not from what the window does."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from desktop.native.material.theme import read_letter_keys, read_shortcuts
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, show_material
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp, turn_on_letter_keys  # noqa: F401

CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
LETTERS = (
    Qt.Key.Key_T,
    Qt.Key.Key_D,
    Qt.Key.Key_W,
    Qt.Key.Key_M,
    Qt.Key.Key_J,
    Qt.Key.Key_K,
    Qt.Key.Key_C,
    Qt.Key.Key_P,
    Qt.Key.Key_Z,
    Qt.Key.Key_F,
)


def _press(
    window: NativeWindow, key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
):
    window.setFocus()
    QTest.keyClick(window, key, modifiers)


def _page(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


@pytest.fixture()
def acted(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What the add, plan and undo keys reach, without opening a sheet that waits for an answer."""
    calls: list[str] = []
    monkeypatch.setattr(window, "_add_now", lambda: calls.append("add"))
    monkeypatch.setattr(window, "_plan_with_left_over", lambda everything=False: calls.append("plan"))
    monkeypatch.setattr(window.session, "undo", lambda: calls.append("undo"))
    return calls


def test_number_keys_open_day_week_month_my_day_and_settings_by_default(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    _press(window, Qt.Key.Key_1)
    wait_until(qapp, lambda: session.planner_view == "day" and not session.busy)
    _press(window, Qt.Key.Key_3)
    wait_until(qapp, lambda: session.planner_view == "month" and not session.busy)
    _press(window, Qt.Key.Key_2)
    wait_until(qapp, lambda: session.planner_view == "week" and not session.busy)
    assert window._day_mode is False
    _press(window, Qt.Key.Key_4)
    assert window._day_mode is True, "4 is My day"
    _press(window, Qt.Key.Key_5)
    assert _page(window) == "settingsPage"


def test_with_number_keys_off_the_number_keys_do_nothing(qapp: QApplication, window: NativeWindow) -> None:
    look_file().write_text(json.dumps({"material": {"shortcuts": False}}))
    for key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5):
        _press(window, key)
        pump(qapp)
        assert window.session.planner_view == "week", key
        assert window._day_mode is False, key
        assert _page(window) == "weekPage", key


def test_by_default_the_letters_do_nothing(
    qapp: QApplication, window: NativeWindow, acted: list[str]
) -> None:
    session = window.session
    home = session.week_start
    for key in LETTERS:
        _press(window, key)
        pump(qapp)
        assert session.planner_view == "week", key
        assert session.week_start == home, key
        assert window._day_mode is False, key
        assert _page(window) == "weekPage", key
    assert acted == []


def test_with_letter_keys_on_d_w_and_m_switch_views(qapp: QApplication, window: NativeWindow) -> None:
    turn_on_letter_keys()
    session = window.session
    for key, view in ((Qt.Key.Key_D, "day"), (Qt.Key.Key_M, "month"), (Qt.Key.Key_W, "week")):
        _press(window, key)
        wait_until(qapp, lambda view=view: session.planner_view == view and not session.busy)


def test_with_letter_keys_on_j_and_k_step_the_week_the_day_and_the_month(
    qapp: QApplication, window: NativeWindow
) -> None:
    turn_on_letter_keys()
    session = window.session
    week = date.fromisoformat(session.week_start)
    _press(window, Qt.Key.Key_J)
    wait_until(
        qapp, lambda: session.week_start == (week + timedelta(days=7)).isoformat() and not session.busy
    )
    _press(window, Qt.Key.Key_K)
    wait_until(qapp, lambda: session.week_start == week.isoformat() and not session.busy)

    _press(window, Qt.Key.Key_D)
    wait_until(qapp, lambda: session.planner_view == "day" and not session.busy)
    shown = date.fromisoformat(session.selected_day)
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.selected_day == (shown + timedelta(days=1)).isoformat())
    _press(window, Qt.Key.Key_K)
    wait_until(qapp, lambda: session.selected_day == shown.isoformat())

    _press(window, Qt.Key.Key_M)
    wait_until(qapp, lambda: session.planner_view == "month" and not session.busy)
    month = session.selected_month
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.selected_month != month)
    _press(window, Qt.Key.Key_K)
    wait_until(qapp, lambda: session.selected_month == month)


def test_with_letter_keys_on_t_goes_to_today(qapp: QApplication, window: NativeWindow) -> None:
    turn_on_letter_keys()
    session = window.session
    home = session.week_start
    _press(window, Qt.Key.Key_J)
    wait_until(qapp, lambda: session.week_start != home and not session.busy)
    _press(window, Qt.Key.Key_T)
    wait_until(qapp, lambda: session.week_start == home and not session.busy)


def test_with_letter_keys_on_c_p_z_and_f_add_plan_undo_and_open_focus(
    qapp: QApplication, window: NativeWindow, acted: list[str]
) -> None:
    turn_on_letter_keys()
    _press(window, Qt.Key.Key_C)
    _press(window, Qt.Key.Key_P)
    _press(window, Qt.Key.Key_Z)
    assert acted == ["add", "plan", "undo"]
    _press(window, Qt.Key.Key_F)
    assert _page(window) == "focusPage"
    assert window.session.focus is None, "F shows the timer; it does not start one"


def test_a_letter_with_shift_or_ctrl_is_not_one_of_the_letter_keys(
    qapp: QApplication, window: NativeWindow, acted: list[str]
) -> None:
    turn_on_letter_keys()
    home = window.session.week_start
    for key in (
        Qt.Key.Key_D,
        Qt.Key.Key_M,
        Qt.Key.Key_J,
        Qt.Key.Key_K,
        Qt.Key.Key_C,
        Qt.Key.Key_P,
        Qt.Key.Key_F,
    ):
        for modifiers in (SHIFT, CTRL):
            if key == Qt.Key.Key_D and modifiers == CTRL:
                continue  # Ctrl+D duplicates the selected block, which is its own shortcut
            _press(window, key, modifiers)
            pump(qapp)
            assert window.session.planner_view == "week", (key, modifiers)
            assert window.session.week_start == home, (key, modifiers)
            assert _page(window) == "weekPage", (key, modifiers)
    assert acted == []


def test_no_key_of_the_set_acts_while_typing_in_a_box(
    qapp: QApplication, window: NativeWindow, acted: list[str]
) -> None:
    turn_on_letter_keys()
    box = QLineEdit(window)
    box.show()
    box.setFocus()
    for key in (Qt.Key.Key_1, Qt.Key.Key_4, *LETTERS):
        QTest.keyClick(box, key)
        pump(qapp)
    assert window.session.planner_view == "week"
    assert window._day_mode is False
    assert _page(window) == "weekPage"
    assert acted == []
    box.deleteLater()


def test_no_key_of_the_set_acts_while_a_dialog_is_open(
    qapp: QApplication, window: NativeWindow, acted: list[str]
) -> None:
    turn_on_letter_keys()
    seen: dict[str, object] = {}
    dialog = QDialog(window)

    def type_into_the_window() -> None:
        for key in (Qt.Key.Key_1, Qt.Key.Key_4, *LETTERS):
            QTest.keyClick(window, key)
            pump(qapp, 3)
        seen["view"] = window.session.planner_view
        seen["day_mode"] = window._day_mode
        dialog.reject()

    QTimer.singleShot(0, type_into_the_window)
    dialog.exec()
    assert seen == {"view": "week", "day_mode": False}
    assert acted == []


def test_ctrl_shortcuts_do_not_answer_to_either_switch(
    qapp: QApplication, window: NativeWindow, acted: list[str]
) -> None:
    look_file().write_text(json.dumps({"material": {"shortcuts": False, "letters": False}}))
    _press(window, Qt.Key.Key_Z, CTRL)
    assert acted == ["undo"]


def _open_settings(window: NativeWindow):
    window._open_settings()
    page = window._settings
    assert page is not None
    return page


def test_the_plain_settings_have_the_two_key_switches_with_letters_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    page = _open_settings(window)
    assert page.number_keys.text() == "Number keys" and page.number_keys.isChecked() is True
    assert page.letter_keys.text() == "Letter keys" and page.letter_keys.isChecked() is False


def test_turning_a_switch_over_saves_it_in_the_settings_material_reads(
    qapp: QApplication, window: NativeWindow
) -> None:
    look_file().write_text(json.dumps({"material": {"preset": "Sea"}, "zoom": {}}))
    page = _open_settings(window)
    page.letter_keys.setChecked(True)
    stored = json.loads(look_file().read_text())
    assert read_letter_keys(stored) is True and read_shortcuts(stored) is True
    page.number_keys.setChecked(False)
    stored = json.loads(look_file().read_text())
    assert read_shortcuts(stored) is False and read_letter_keys(stored) is True
    assert stored["material"]["preset"] == "Sea", "the rest of Material's settings stay as they were"
    assert "zoom" in stored, "so does the rest of the look file"
    page.letter_keys.setChecked(False)
    assert read_letter_keys(json.loads(look_file().read_text())) is False


def test_a_switch_turned_over_in_one_look_is_turned_over_in_the_other(
    qapp: QApplication, window: NativeWindow
) -> None:
    page = _open_settings(window)
    page.letter_keys.setChecked(True)
    page.number_keys.setChecked(False)
    show_material(qapp, window)
    bridge = window._material_page.bridge
    assert bridge.property("letterKeys") is True and bridge.property("shortcuts") is False
    # And back: Material turns Letter keys off and the plain page shows it off.
    bridge.settingsBridge.setLetterKeys(False)
    bridge.settingsBridge.setShortcuts(True)
    window._use_widgets_styles()
    pump(qapp)
    page = _open_settings(window)
    assert page.letter_keys.isChecked() is False and page.number_keys.isChecked() is True
