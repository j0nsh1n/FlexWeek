"""Layouts in the real window, against a real local backend: My day puts planning away and brings it
back, a day screen's buttons reach the behaviour the product already has, the choice survives a
restart, and the Layout dialog shows its three levels.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QPushButton

    from desktop.native.calendar import sunday_due
    from desktop.native.layouts.dialog import LayoutDialog
    from desktop.native.layouts.one_thing import OneThingView
    from desktop.native.layouts.registry import LAYOUTS
    from desktop.native.layouts.views import VIEW_CLASSES
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer

PASSWORD = "a-long-test-password"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-layouts-window-test"])
    yield application


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def settled(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


@pytest.fixture()
def window(qapp: QApplication, tmp_path: Path) -> Iterator[NativeWindow]:
    """Signed in on this week with school, dinner and an essay planned for Thursday evening, and the
    clock held at Thursday 19:00 so the tests do not depend on the day they run."""
    look_file().unlink(missing_ok=True)
    server = LocalServer(tmp_path / "flexweek.db", serve_frontend=False)
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    try:
        made.username.setText("layout_student")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        wait_until(
            qapp, lambda: made._stack.currentWidget().objectName() == "weekPage" and not made.session.busy
        )
        wait_until(qapp, lambda: made.session.preferences is not None)
        session = made.session
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=19)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
        session.add_block(
            {
                "id": "school",
                "title": "School",
                "kind": "locked",
                "category": "class",
                "start": "08:00",
                "duration_min": 390,
                "days": [0, 1, 2, 3, 4],
            }
        )
        session.add_homework(
            {
                "id": "essay",
                "title": "History essay",
                "due": sunday_due(session.week_start),
                "estimate_min": 60,
                "revision": 0,
            }
        )
        session.save()
        settled(qapp, made)
        work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
        work.update({"start": "18:45", "days": [3], "duration_min": 60})
        session.add_block(work)
        session.save()
        settled(qapp, made)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()
        look_file().unlink(missing_ok=True)


def click(window: NativeWindow, name: str) -> None:
    window.findChild(QPushButton, name).click()


def test_my_day_puts_planning_away_and_back_brings_it_back(qapp: QApplication, window: NativeWindow) -> None:
    assert window.planner.currentWidget() is window.week_table
    click(window, "viewMyDay")
    assert isinstance(window.planner.currentWidget(), OneThingView)
    assert window.plan_chrome.isVisible() is False
    assert window.findChild(QPushButton, "viewMyDay").isChecked() is True
    assert window.findChild(QPushButton, "viewWeek").isChecked() is False
    click(window, "oneBack")
    assert window.planner.currentWidget() is window.week_table
    assert window.plan_chrome.isVisible() is True
    assert window.findChild(QPushButton, "viewWeek").isChecked() is True


def test_the_day_screen_reads_the_real_week_at_the_real_minute(
    qapp: QApplication, window: NativeWindow
) -> None:
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    said = tuple(view.findChild(QLabel, name).text() for name in ("oneLabel", "oneTitle", "oneLine"))
    assert said == ("NOW", "HISTORY ESSAY", "UNTIL 19:45 · 45 MIN LEFT")


def test_homework_finished_finishes_it_the_way_the_product_does(
    qapp: QApplication, window: NativeWindow
) -> None:
    click(window, "viewMyDay")
    click(window, "oneFinished")
    settled(qapp, window)
    assert window.session.assignments["essay"]["completed"] is True
    assert window.session.can_undo() is True
    view = window.planner.currentWidget()
    assert view.findChild(QLabel, "oneTitle").text() == "NOTHING ELSE TODAY"


def test_start_focus_keeps_the_timer_in_view_on_a_day_screen(
    qapp: QApplication, window: NativeWindow
) -> None:
    click(window, "viewMyDay")
    assert window.focus_panel.isVisible() is False
    click(window, "oneFocus")
    wait_until(qapp, lambda: window.session.focus is not None)
    assert window.session.focus["title"] == "History essay"
    assert window.focus_panel.isVisible() is True
    assert window.plan_chrome.isVisible() is False


def test_running_late_opens_the_products_own_running_late(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(NativeWindow, "_open_late", lambda self: opened.append("late"))
    click(window, "viewMyDay")
    click(window, "oneLate")
    assert opened == ["late"]


def test_the_keyboard_reaches_my_day_and_back(qapp: QApplication, window: NativeWindow) -> None:
    window.week_table.setFocus()
    QTest.keyClick(window, Qt.Key.Key_T)
    assert isinstance(window.planner.currentWidget(), OneThingView)
    QTest.keyClick(window, Qt.Key.Key_B)
    assert window.planner.currentWidget() is window.week_table
    QTest.keyClick(window, Qt.Key.Key_T)
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert window.planner.currentWidget() is window.week_table
    QTest.keyClick(window, Qt.Key.Key_T)
    QTest.keyClick(window, Qt.Key.Key_M)
    wait_until(qapp, lambda: window.planner.currentWidget() is window.month_grid)
    assert window.plan_chrome.isVisible() is True


def test_the_view_buttons_leave_a_day_screen(qapp: QApplication, window: NativeWindow) -> None:
    click(window, "viewMyDay")
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_agenda
    assert window.plan_chrome.isVisible() is True


def test_signing_out_of_a_day_screen_does_not_leave_the_next_student_in_one(
    qapp: QApplication, window: NativeWindow
) -> None:
    click(window, "viewMyDay")
    click(window, "signOut")
    wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "authPage")
    assert window._day_mode is False


def test_the_choice_is_saved_on_this_device_beside_the_look(qapp: QApplication, window: NativeWindow) -> None:
    window._look = {"preset": "paper", "knobs": {"corners": "pill"}}
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"colour": "paper"}}}
    window._save_look()
    assert json.loads(look_file().read_text()) == {
        "preset": "paper",
        "knobs": {"corners": "pill"},
        "layout": {"main": "classic", "day": "one", "options": {"one": {"colour": "paper"}}},
    }
    window._look, window._layout = {}, {}
    window._load_look()
    assert window._look == {"preset": "paper", "knobs": {"corners": "pill"}}
    assert window._layout["options"] == {"one": {"colour": "paper"}}
    click(window, "viewMyDay")
    assert window.planner.currentWidget().grab().toImage().pixelColor(4, 4).name() == "#f7f1e3"


def test_a_look_file_from_before_layouts_still_loads(qapp: QApplication, window: NativeWindow) -> None:
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps({"preset": "terminal", "knobs": {}}))
    window._load_look()
    assert window._look["preset"] == "terminal"
    assert window._layout == {"main": "classic", "day": "one", "options": {}}
    look_file().write_text("not json")
    window._load_look()
    assert window._layout == {"main": "classic", "day": "one", "options": {}}


def test_saving_the_look_from_settings_keeps_the_layout(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"daybar": "hide"}}}
    window._look = {"preset": "ink", "knobs": {}}
    window._save_look()
    assert json.loads(look_file().read_text())["layout"]["options"] == {"one": {"daybar": "hide"}}


def test_a_changed_look_repaints_a_design_that_matches_it(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {"one": {"colour": "match"}}}
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    before = view.grab().toImage().pixelColor(4, 4).name()
    window._look = {"preset": "terminal", "knobs": {}}
    window._apply_appearance()
    after = view.grab().toImage().pixelColor(4, 4).name()
    assert before != after
    assert after == view.scene.tokens["bg"]


def combo(dialog: LayoutDialog, name: str) -> QComboBox:
    return dialog.findChild(QComboBox, name)


def rows(dialog: LayoutDialog, slot: str) -> list[str]:
    return sorted(
        box.objectName()
        for box in dialog.findChildren(QComboBox)
        if box.objectName().startswith(f"layout{slot}-")
    )


def test_the_dialog_shows_style_first_and_fine_tune_on_request(qapp: QApplication) -> None:
    dialog = LayoutDialog(None, None)
    assert [combo(dialog, "layoutDay").itemText(index) for index in range(2)] == ["One thing", "Day dial"]
    assert rows(dialog, "Day") == ["layoutDay-colour"]
    dialog.findChild(QCheckBox, "layoutDayMore").setChecked(True)
    assert rows(dialog, "Day") == [
        "layoutDay-actions",
        "layoutDay-colour",
        "layoutDay-daybar",
        "layoutDay-lead",
    ]
    assert rows(dialog, "Main") == []
    assert dialog.findChild(QLabel, "layoutMainSummary").text() == LAYOUTS["classic"].summary


def test_the_dialog_stores_only_what_the_student_changed(qapp: QApplication) -> None:
    dialog = LayoutDialog(None, None)
    assert dialog.choice() == {"main": "classic", "day": "one", "options": {}}
    colour = combo(dialog, "layoutDay-colour")
    colour.setCurrentIndex(colour.findData("paper"))
    assert dialog.choice() == {"main": "classic", "day": "one", "options": {"one": {"colour": "paper"}}}
    colour = combo(dialog, "layoutDay-colour")
    colour.setCurrentIndex(colour.findData("black"))
    assert dialog.choice()["options"] == {}


def test_fine_tuning_already_in_use_is_not_hidden(qapp: QApplication) -> None:
    dialog = LayoutDialog(None, {"options": {"one": {"daybar": "hide"}}})
    assert dialog.findChild(QCheckBox, "layoutDayMore").isChecked() is True
    assert combo(dialog, "layoutDay-daybar").currentData() == "hide"


def test_trying_another_design_and_coming_back_loses_nothing(qapp: QApplication) -> None:
    dialog = LayoutDialog(None, {"options": {"one": {"colour": "paper"}}})
    pick = combo(dialog, "layoutDay")
    pick.setCurrentIndex(pick.findData("dial"))
    assert combo(dialog, "layoutDay-colour").currentData() == "midnight"
    pick.setCurrentIndex(pick.findData("one"))
    assert combo(dialog, "layoutDay-colour").currentData() == "paper"
    assert dialog.choice()["options"] == {"one": {"colour": "paper"}}


def test_a_design_can_be_put_back_to_its_own_settings(qapp: QApplication) -> None:
    dialog = LayoutDialog(None, {"options": {"one": {"colour": "paper", "lead": "next"}}})
    dialog.findChild(QPushButton, "layoutDayReset").click()
    assert dialog.choice()["options"] == {}
    assert dialog.findChild(QCheckBox, "layoutDayMore").isChecked() is False


def test_every_built_view_is_a_design_in_the_registry(qapp: QApplication) -> None:
    assert set(VIEW_CLASSES) <= set(LAYOUTS) - {"classic"}
    assert all(view.layout_id == layout_id for layout_id, view in VIEW_CLASSES.items())


def test_my_day_opens_whichever_day_screen_was_picked(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "dial", "options": {}}
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    assert type(view).__name__ == "DayDialView"
    assert view.findChild(QLabel, "dialTitle").text() == "History essay"
    click(window, "dialBack")
    assert window.planner.currentWidget() is window.week_table


def tool_actions(window: NativeWindow) -> dict[str, bool]:
    menu = window.tools_button.menu()
    menu.aboutToShow.emit()
    return {action.text(): action.isEnabled() for action in menu.actions() if action.text()}


def test_a_design_of_its_own_gets_the_window_and_tools_holds_the_controls(
    qapp: QApplication, window: NativeWindow
) -> None:
    assert window.tools_button.isVisible() is False
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    assert type(window.planner.currentWidget()).__name__ == "BentoView"
    assert window.plan_chrome.isVisible() is False
    assert window.tools_button.isVisible() is True
    qapp.processEvents()
    assert window.planner.height() > window.height() * 0.8
    offered = tool_actions(window)
    assert list(offered)[:6] == ["Add fixed time", "Add homework", "Plan my homework", "Undo", "Redo", "Save"]
    assert {"Settings", "Running late", "Routines", "Account", "Reload"} <= set(offered)
    assert (offered["Undo"], offered["Redo"]) == (True, False)


def test_a_tool_does_what_its_button_does(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    before = len(window.session.blocks)
    menu = window.tools_button.menu()
    next(action for action in menu.actions() if action.text() == "Undo").trigger()
    settled(qapp, window)
    assert len(window.session.blocks) != before or window.session.can_redo() is True


def test_day_and_month_keep_the_planning_controls(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_agenda
    assert (window.plan_chrome.isVisible(), window.tools_button.isVisible()) == (True, False)
    click(window, "viewWeek")
    assert (window.plan_chrome.isVisible(), window.tools_button.isVisible()) == (False, True)
    click(window, "viewMyDay")
    assert (window.plan_chrome.isVisible(), window.tools_button.isVisible()) == (False, False)


def test_bentos_buttons_reach_the_products_own_add_and_plan(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr(NativeWindow, "_add_homework", lambda self: asked.append("add"))
    monkeypatch.setattr(type(window.session), "solve", lambda self: asked.append("plan"))
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    click(window, "bentoAdd")
    click(window, "bentoPlan")
    click(window, "bentoMyDay")
    assert asked == ["add", "plan"]
    assert type(window.planner.currentWidget()).__name__ == "OneThingView"
