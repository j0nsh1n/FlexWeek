# ruff: noqa: F811
"""Keyboard use of the Material sheets: Esc closes a sheet and the keyboard goes back to the Add button,
Esc on the discard question keeps editing, and Tab and Shift+Tab stay inside a sheet, skip what is hidden
or off, and wrap both ways; sheets opened from the More menu take the keyboard.

Expected focus names come from the sheet's controls, not from reading the focus order the QML computes.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import named, pump, qml, show_material, visuals  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    DISCARD,
    find_named,
    open_light,
    qapp,
    settle,
    sheets,
    shell,
    type_homework,
)


def test_esc_closes_a_sheet_and_the_keyboard_goes_back_to_the_add_button(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    fab = qml(root, "materialFab")
    fab.forceActiveFocus()
    pump(qapp)
    sheets.openHomework()
    pump(qapp, 60)
    held = quick.quickWindow().activeFocusItem()
    assert held is not None
    assert held.objectName() != "materialFab"
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp)
    assert sheets.kind == ""
    assert quick.quickWindow().activeFocusItem() is fab


def test_the_discard_prompt_shows_in_qml_and_esc_keeps_editing(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = show_material(qapp, shell)
    quick = shell._material_page._quick
    shell.activateWindow()
    quick.setFocus()
    sheets.openHomework()
    type_homework(sheets, "Typed")
    pump(qapp, 60)
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp, 40)
    assert sheets.ask["title"] == DISCARD
    assert find_named(root, "prompt_keep") is not None
    assert find_named(root, "prompt_discard") is not None
    QTest.keyClick(quick, Qt.Key.Key_Escape)
    pump(qapp, 40)
    assert sheets.ask == {}
    assert sheets.kind == "homework"


GENERIC_FOCUS = {
    "",
    "fieldInput",
    "shape",
    "label",
    "pickerValue",
    "pickerList",
    "sheetBody",
    "sheetCard",
    "sheetHost",
    "sheetTitle",
    "homeworkSheet",
    "blockSheet",
    "lateSheet",
    "homeworkDetails",
    "homeworkPrompt",
    "blockPrompt",
    "materialShell",
    "promptCard",
    "savePrompt",
    "importPrompt",
    "exportPrompt",
    "presetPrompt",
    "sheetPrompt",
}
SHEET_OWNERS = (
    "sheetHost",
    "homeworkSheet",
    "blockSheet",
    "lateSheet",
    "sheetCard",
    "sheetPrompt",
    "pickerList",
)
UNDERLAY = (
    "weekBlock",
    "homeworkCard",
    "navWeek",
    "navDay",
    "navMonth",
    "navMyDay",
    "navSettings",
    "materialFab",
    "materialSnackbar",
    "materialRail",
    "materialUndo",
    "materialRedo",
    "materialMore",
    "weekPrevious",
    "weekNext",
)
HIDDEN_ON_HOMEWORK_EDIT = (
    "homeworkBack",
    "homeworkDueTimePhone",
    "homeworkCourse",
    "homeworkNotes",
    "homeworkCrumb0",
)


def _lineage(item: QObject | None) -> list[str]:
    names: list[str] = []
    while item is not None:
        names.append(str(item.objectName() or type(item).__name__))
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return names


def _focused(shell: NativeWindow) -> QObject | None:
    return shell._material_page._quick.quickWindow().activeFocusItem()


def _semantic(chain: list[str]) -> str:
    for name in chain:
        if name.startswith("QQuick"):
            continue
        if name in GENERIC_FOCUS:
            continue
        return name
    return chain[0] if chain else "(none)"


def _press(qapp: QApplication, shell: NativeWindow, key: Qt.Key) -> list[str]:
    QTest.keyClick(shell._material_page._quick, key)
    pump(qapp, 3)
    return _lineage(_focused(shell))


def _item_enabled(item: QObject | None) -> bool:
    while item is not None:
        value = item.property("enabled") if hasattr(item, "property") else None
        if value is False:
            return False
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return True


def _week_marks(shell: NativeWindow) -> tuple:
    return tuple(
        (
            str(block.get("id")),
            block.get("start"),
            tuple(block.get("days") or []),
            bool(block.get("completed")),
        )
        for block in shell.session.blocks
    )


def _cycle_names(
    qapp: QApplication, shell: NativeWindow, start: str, key: Qt.Key, owners: tuple[str, ...]
) -> list[str]:
    names: list[str] = []
    for _ in range(24):
        chain = _press(qapp, shell, key)
        name = _semantic(chain)
        assert any(owner in chain for owner in owners), f"{key} left the overlay at {name}: {chain}"
        assert not any(leak in chain for leak in UNDERLAY), f"{key} reached the underlay: {chain}"
        assert _item_enabled(_focused(shell)), f"{name} was not enabled: {chain}"
        if not names:
            assert name != start, f"{key} did not leave {start}: {chain}"
        if name == start:
            return names
        names.append(name)
    raise AssertionError(f"{key} never wrapped back to {start}; visited {names}")


def test_homework_sheet_tab_cycles_enabled_controls_and_wraps_both_ways(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = shell._material_page.root
    nav = qml(root, "navWeek")
    nav.forceActiveFocus()
    pump(qapp)
    marks = _week_marks(shell)
    done = bool(shell.session.assignments["essay"].get("completed"))
    screen = shell._material_page.bridge.property("screen")
    sheets.editHomework("essay")
    pump(qapp)
    assert sheets.kind == "homework"
    start_chain = _lineage(_focused(shell))
    start = _semantic(start_chain)
    assert start == "homeworkTitle", f"initial focus was {start}: {start_chain}"
    assert "homeworkSheet" in start_chain
    essay = next(block for block in named(root, "weekBlock") if block.property("title") == "History essay")
    assert essay.property("enabled") is False
    assert qml(root, "materialFab").property("enabled") is False

    forward = _cycle_names(qapp, shell, start, Qt.Key.Key_Tab, SHEET_OWNERS)
    assert len(forward) == len(set(forward)), f"Tab repeated a control: {forward}"
    assert len(forward) >= 8, f"Tab visited too few controls: {forward}"
    for name in (
        "homeworkDue",
        "homeworkDueTime",
        "homeworkWhen",
        "homeworkQuick",
        "homeworkCompleted",
        "homeworkMoreDetails",
        "deleteHomework",
        "homeworkCancel",
        "homeworkNext",
    ):
        assert name in forward, f"{name} missing from {forward}"
    for name in HIDDEN_ON_HOMEWORK_EDIT:
        assert name not in forward, f"hidden {name} was in {forward}"

    backward = _cycle_names(qapp, shell, start, Qt.Key.Key_Backtab, SHEET_OWNERS)
    assert backward == list(reversed(forward)), f"Backtab {backward} was not the reverse of {forward}"
    assert _semantic(_lineage(_focused(shell))) == start
    assert _week_marks(shell) == marks
    assert bool(shell.session.assignments["essay"].get("completed")) is done
    assert shell._material_page.bridge.property("screen") == screen

    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    pump(qapp, 8)
    assert sheets.kind == ""
    restored = _lineage(_focused(shell))
    assert "navWeek" in restored
    assert essay.property("enabled") is True
    assert qml(root, "materialFab").property("enabled") is True
    assert _week_marks(shell) == marks

    sheets.editHomework("essay")
    pump(qapp)
    due = find_named(root, "homeworkDue")
    due.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Space)
    pump(qapp, 8)
    scene = shell._material_page._quick.quickWindow().contentItem()
    lists = [item for item in visuals(scene) if str(item.objectName()) == "pickerList"]
    assert lists, f"due picker did not open; focus={_lineage(_focused(shell))}"
    for index in range(4):
        chain = _press(qapp, shell, Qt.Key.Key_Tab)
        assert "pickerList" in chain or "Popup" in chain, f"picker Tab {index} left the list: {chain}"
        assert "weekBlock" not in chain
        assert "homeworkNext" not in chain
        assert "navWeek" not in chain
    sheets.forceClose()
    pump(qapp, 5)


def test_fixed_time_sheet_tab_wraps_inside_and_skips_hidden_controls(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    marks = _week_marks(shell)
    sheets.editBlock("school", 0)
    pump(qapp)
    assert sheets.kind == "block"
    start_chain = _lineage(_focused(shell))
    start = _semantic(start_chain)
    assert start == "blockTitle", f"initial focus was {start}: {start_chain}"
    forward = _cycle_names(qapp, shell, start, Qt.Key.Key_Tab, SHEET_OWNERS)
    assert len(forward) == len(set(forward)), f"Tab repeated a control: {forward}"
    assert len(forward) >= 5, f"Tab visited too few controls: {forward}"
    for name in ("blockCancel", "blockNext"):
        assert name in forward, f"{name} missing from {forward}"
    assert "blockBack" not in forward
    backward = _cycle_names(qapp, shell, start, Qt.Key.Key_Backtab, SHEET_OWNERS)
    assert backward == list(reversed(forward)), f"Backtab {backward} was not the reverse of {forward}"
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    pump(qapp, 5)
    assert sheets.kind == ""
    assert _week_marks(shell) == marks


def _open_from_more(qapp: QApplication, shell: NativeWindow, sheets, action: str) -> None:
    shell.activateWindow()
    shell._material_page._quick.setFocus()
    qml(shell._material_page.root, "materialFab").forceActiveFocus()
    pump(qapp)
    sheets.openMore()
    pump(qapp, 10)
    sheets.moreAction(action)
    pump(qapp, 10)


def test_running_late_from_more_takes_the_keyboard_and_tab_stays_in_the_sheet(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_from_more(qapp, shell, sheets, "runningLate")
    assert sheets.kind == "late"
    chain = _lineage(_focused(shell))
    assert "lateMinutes" in chain, chain
    chain = _press(qapp, shell, Qt.Key.Key_Tab)
    assert "lateSheet" in chain and "lateMinutes" not in chain, chain


def test_unfinished_from_more_takes_the_keyboard(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    session = shell.session
    session.add_homework(
        {
            "id": "lab-writeup",
            "title": "Lab write-up",
            "due": f"{session.week_start}T09:00",
            "estimate_min": 45,
            "revision": 0,
        }
    )
    session.save()
    settle(qapp, shell)
    _open_from_more(qapp, shell, sheets, "unfinishedOpen")
    assert sheets.kind == "unfinished"
    assert "unfinishedSheet" in _lineage(_focused(shell))
    assert "unfinishedSheet" in _press(qapp, shell, Qt.Key.Key_Tab)


def _open_pinned_time_field(qapp: QApplication, shell: NativeWindow, sheets, day: int = 4) -> QObject:
    """Friday by default: today's list starts at the clock (19:00), so a whole list needs a day ahead. The
    student drags in quarter hours here, so the list is quarter hours."""
    shell.session.preferences = {**(shell.session.preferences or {}), "drag_step_min": 15}
    sheets.editHomework("essay")
    pump(qapp)
    sheets.setText("when", "fixed")
    sheets.setNumber("whenDay", day)
    sheets.setText("whenTime", "19:00")
    pump(qapp)
    root = shell._material_page._quick.rootObject()
    field = find_named(root, "homeworkWhenTime")
    field.forceActiveFocus()
    pump(qapp)
    return field


def test_pinned_time_list_opens_on_the_chosen_time(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _open_pinned_time_field(qapp, shell, sheets)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Space)
    pump(qapp, 8)
    scene = shell._material_page._quick.quickWindow().contentItem()
    lists = [item for item in visuals(scene) if str(item.objectName()) == "pickerList"]
    assert lists, "the pinned time list did not open"
    picker = lists[0]
    seven_pm = 19 * 4
    assert picker.property("currentIndex") == seven_pm
    top = picker.property("contentY")
    assert top <= seven_pm * 44 < top + picker.property("height"), (
        f"7:00 PM (row {seven_pm}) is off screen: the list starts at {top}"
    )
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Escape)
    pump(qapp, 5)
    sheets.forceClose()
    pump(qapp, 5)


def test_pinned_time_moves_with_up_and_down_on_the_closed_field(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_pinned_time_field(qapp, shell, sheets)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Up)
    pump(qapp, 5)
    assert sheets.form["whenTime"] == "18:45"
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Down)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Down)
    pump(qapp, 5)
    assert sheets.form["whenTime"] == "19:15"
    sheets.forceClose()
    pump(qapp, 5)


def test_up_on_todays_pinned_time_stops_at_the_earliest_time_allowed(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_pinned_time_field(qapp, shell, sheets, day=3)
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Up)
    pump(qapp, 5)
    assert sheets.form["whenTime"] == "19:00", "the clock reads 19:00: nothing earlier is offered today"
    QTest.keyClick(shell._material_page._quick, Qt.Key.Key_Down)
    pump(qapp, 5)
    assert sheets.form["whenTime"] == "19:15"
    sheets.forceClose()
    pump(qapp, 5)
