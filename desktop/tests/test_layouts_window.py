"""Layouts in the real window, against a real local backend: My day puts planning away and brings it
back, a day screen's buttons reach the behaviour the product already has, the choice survives a
restart, and Settings holds Main view and Day screen with their three levels.
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
    from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLabel, QPushButton

    from desktop.native.calendar import sunday_due
    from desktop.native.layouts.one_thing import OneThingView
    from desktop.native.layouts.registry import LAYOUTS, sanitize_layout
    from desktop.native.layouts.views import VIEW_CLASSES
    from desktop.native.settings import PrefsDialog
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
    server = LocalServer(tmp_path / "flexweek.db")
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
    assert window.solve_button.isVisible() is True
    assert window.findChild(QPushButton, "viewMyDay").isChecked() is True
    assert window.findChild(QPushButton, "viewWeek").isChecked() is False
    click(window, "oneBack")
    assert window.planner.currentWidget() is window.week_table
    assert window.solve_button.isVisible() is True
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
    assert window.solve_button.isVisible() is True


def test_running_late_opens_the_products_own_running_late(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(NativeWindow, "_open_late", lambda self: opened.append("late"))
    click(window, "viewMyDay")
    click(window, "oneLate")
    assert opened == ["late"]


def test_a_blocked_running_late_toasts_why(qapp: QApplication, window: NativeWindow) -> None:
    from desktop.native.widgets import TOAST_MS

    window.session.dirty = True
    window._open_late()
    saving = "Your last change is still saving. Try again in a moment."
    assert window.toast.isVisible() is True
    assert window.toast.text() == saving
    assert window.week_status.text() == saving
    assert window.toast._timer.interval() == TOAST_MS

    window.session.dirty = False
    window.session.conflict = True
    window._open_late()
    conflict = "This week was changed somewhere else. Reload it first."
    assert window.toast.text() == conflict
    assert window.week_status.text() == conflict


def test_the_notice_sits_under_the_bar_on_one_line(qapp: QApplication, window: NativeWindow) -> None:
    """A notice short enough for one line stays on one line, and it never covers the bar. Sized from
    a wrapped label it broke after "locked. 2", and pinned 52 pixels down it covered the bottom of
    Day, Week, Month and My day once large text made the bar taller."""
    said = "Running late: 16:30–17:00 is now locked. 2 moved."
    for text in ("normal", "large"):
        window._look = {**window._look, "knobs": {**(window._look.get("knobs") or {}), "text": text}}
        window._apply_appearance()
        settled(qapp, window)
        window.toast.show_message("OK")
        one_line = window.toast.height()
        window.toast.show_message(said)
        settled(qapp, window)
        bar_bottom = max(
            button.mapTo(window, button.rect().bottomLeft()).y()
            for button in (window.solve_button, window.more_button, window.settings_gear)
        )
        assert (text, window.toast.height()) == (text, one_line)
        assert window.toast.y() > bar_bottom, text


def accept_late(qapp: QApplication, window: NativeWindow) -> tuple[dict, str]:
    from desktop.native.reuse import late_locked_line

    now = datetime.fromtimestamp(window.session.now_ms() / 1000)
    window.session.preview_running_late(30, now)
    wait_until(qapp, lambda: window.session.late_preview is not None and not window.session.busy)
    preview = window.session.late_preview
    moved = len((preview.get("trace") or {}).get("moves") or [])
    window._commit_late(preview)
    return preview["block"], late_locked_line(preview["block"], moved)


def test_accepting_running_late_says_locked_once_it_is_saved(
    qapp: QApplication, window: NativeWindow
) -> None:
    block, said = accept_late(qapp, window)
    assert window.session.selected_block_id == block["id"]
    # Nothing is said before the save answers: until then the late start is not kept anywhere.
    assert window.toast.isVisible() is False
    wait_until(qapp, lambda: window.toast.isVisible())
    assert window.toast.text() == said
    assert window.session.dirty is False
    assert any(item["id"] == block["id"] for item in window.session.blocks)


def test_a_save_without_the_late_start_does_not_confirm_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A save already in flight when Running late was accepted stores the week without it."""
    window._late_waiting = ("b-late-not-stored-yet", "Running late: 19:00–19:30 is now locked.")
    window.session.save_finished.emit(True, "Saved.")
    qapp.processEvents()
    assert window.toast.isVisible() is False


def test_a_late_start_that_fails_to_save_says_so_instead(qapp: QApplication, window: NativeWindow) -> None:
    from desktop.tests.logic_support import fail_once

    fail_once(window.session, "POST", "/api/changes", 409)
    _block, said = accept_late(qapp, window)
    wait_until(qapp, lambda: window.toast.isVisible())
    assert window.toast.text() != said
    assert window.toast.text().startswith("Not saved.")
    assert window.session.conflict is True


def test_the_keyboard_reaches_my_day_and_back(qapp: QApplication, window: NativeWindow) -> None:
    """The week grid keeps letter keys for type-ahead, so T has to be taken the way W, D and M are."""
    QTest.keyClick(window.week_table, Qt.Key.Key_T)
    day = window.planner.currentWidget()
    assert isinstance(day, OneThingView)
    QTest.keyClick(day, Qt.Key.Key_B)
    assert window.planner.currentWidget() is window.week_table
    QTest.keyClick(window.week_table, Qt.Key.Key_T)
    QTest.keyClick(window.planner.currentWidget(), Qt.Key.Key_Escape)
    assert window.planner.currentWidget() is window.week_table
    QTest.keyClick(window.week_table, Qt.Key.Key_T)
    QTest.keyClick(window.planner.currentWidget(), Qt.Key.Key_M)
    wait_until(qapp, lambda: window.planner.currentWidget() is window.month_grid)
    assert window.solve_button.isVisible() is True
    QTest.keyClick(window.month_grid.table, Qt.Key.Key_T)
    assert isinstance(window.planner.currentWidget(), OneThingView)


def test_the_view_buttons_leave_a_day_screen(qapp: QApplication, window: NativeWindow) -> None:
    click(window, "viewMyDay")
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_agenda
    assert window.solve_button.isVisible() is True


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
    stored = json.loads(look_file().read_text())
    assert stored["preset"] == "paper"
    assert stored["knobs"] == {"corners": "pill"}
    assert stored["layout"] == {
        "main": "classic",
        "day": "one",
        "options": {"one": {"colour": "paper"}},
    }
    # Whether this computer checks for updates lives beside the look, because it is a property of
    # the computer rather than the account.
    assert set(stored["updates"]) == {"check", "last_ms", "skip"}
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


def combo(dialog: PrefsDialog, name: str) -> QComboBox:
    return dialog.findChild(QComboBox, name)


def rows(dialog: PrefsDialog, slot: str) -> list[str]:
    return sorted(
        box.objectName()
        for box in dialog.findChildren(QComboBox)
        if box.objectName().startswith(f"layout{slot}-")
    )


def prefs_layout(choice: dict | None = None) -> PrefsDialog:
    return PrefsDialog(None, {}, {}, {}, choice)


def test_the_dialog_shows_style_first_and_fine_tune_on_request(qapp: QApplication) -> None:
    dialog = prefs_layout()
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
    dialog = prefs_layout()
    assert dialog.layout_choice() == {"main": "classic", "day": "one", "options": {}}
    colour = combo(dialog, "layoutDay-colour")
    colour.setCurrentIndex(colour.findData("paper"))
    assert dialog.layout_choice()["options"] == {"one": {"colour": "paper"}}
    colour = combo(dialog, "layoutDay-colour")
    colour.setCurrentIndex(colour.findData("black"))
    assert dialog.layout_choice()["options"] == {}


def test_fine_tuning_already_in_use_is_not_hidden(qapp: QApplication) -> None:
    dialog = prefs_layout({"options": {"one": {"daybar": "hide"}}})
    assert dialog.findChild(QCheckBox, "layoutDayMore").isChecked() is True
    assert combo(dialog, "layoutDay-daybar").currentData() == "hide"


def test_trying_another_design_and_coming_back_loses_nothing(qapp: QApplication) -> None:
    dialog = prefs_layout({"options": {"one": {"colour": "paper"}}})
    pick = combo(dialog, "layoutDay")
    pick.setCurrentIndex(pick.findData("dial"))
    assert combo(dialog, "layoutDay-colour").currentData() == "midnight"
    pick.setCurrentIndex(pick.findData("one"))
    assert combo(dialog, "layoutDay-colour").currentData() == "paper"
    assert dialog.layout_choice()["options"] == {"one": {"colour": "paper"}}


def test_a_design_can_be_put_back_to_its_own_settings(qapp: QApplication) -> None:
    dialog = prefs_layout({"options": {"one": {"colour": "paper", "lead": "next"}}})
    dialog.findChild(QPushButton, "layoutDayReset").click()
    assert dialog.layout_choice()["options"] == {}
    assert dialog.findChild(QCheckBox, "layoutDayMore").isChecked() is False
    assert dialog.findChild(QPushButton, "layoutDayReset").text() == "Reset this layout's options"


def test_every_built_view_is_a_design_in_the_registry(qapp: QApplication) -> None:
    # Today's app is the week grid itself, so it is the one design with no view of its own.
    assert set(VIEW_CLASSES) == set(LAYOUTS) - {"classic"}
    assert all(view.layout_id == layout_id for layout_id, view in VIEW_CLASSES.items())


def test_my_day_opens_whichever_day_screen_was_picked(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "dial", "options": {}}
    click(window, "viewMyDay")
    view = window.planner.currentWidget()
    assert type(view).__name__ == "DayDialView"
    assert view.findChild(QLabel, "dialTitle").text() == "History essay"
    click(window, "dialBack")
    assert window.planner.currentWidget() is window.week_table


def test_summaries_speak_minutes_not_session_counts(
    qapp: QApplication, window: NativeWindow
) -> None:
    import re

    from PySide6.QtWidgets import QListWidget

    sessions = re.compile(r"\b0 sessions?\b")

    def labels() -> list[str]:
        found = [lab.text() for lab in window.findChildren(QLabel) if lab.text()]
        for box in window.findChildren(QListWidget):
            found.extend(box.item(index).text() for index in range(box.count()))
        return found

    window.focus_panel.set_state(window.session)

    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert "1 h planned · 0 done" in shown
    assert not any(sessions.search(text) for text in shown)

    window._layout = {"main": "timeline", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert any("1 h planned · 0 done" in text for text in shown)
    assert not any(sessions.search(text) for text in shown)

    click(window, "viewMyDay")
    click(window, "oneFinished")
    settled(qapp, window)
    click(window, "viewWeek")
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert any("1 h planned · 1 h done" in text for text in shown)
    assert not any(sessions.search(text) for text in shown)


def more_actions(window: NativeWindow) -> dict[str, bool]:
    """The items, without the section headings. addSection makes a separator that carries text.
    Advanced is a submenu, so its entries are included under their own names."""
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    offered: dict[str, bool] = {}
    for action in menu.actions():
        if action.isSeparator() or not action.text() or not action.isVisible():
            continue
        submenu = action.menu()
        if submenu is None:
            offered[action.text()] = action.isEnabled()
            continue
        offered[action.text()] = action.isEnabled()
        for inner in submenu.actions():
            if inner.text() and not inner.isSeparator() and inner.isVisible():
                offered[inner.text()] = inner.isEnabled()
    return offered


def more_sections(window: NativeWindow) -> list[str]:
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    return [action.text() for action in menu.actions() if action.isSeparator() and action.text()]


def test_plan_and_more_stay_on_the_bar_in_every_layout(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A design of its own used to hide Plan my homework and More behind Tools. That rule is gone:
    the same two buttons stay in the top bar in every layout, every view, and My day."""
    assert window.findChild(QPushButton, "toolsButton") is None
    sections = None
    items = None
    for main in ("classic", "bento", "timeline"):
        window._layout = {"main": main, "day": "one", "options": {}}
        window._on_week()
        assert window.solve_button.isVisible() is True
        assert window.more_button.isVisible() is True
        assert window.more_button.text() == "More"
        if sections is None:
            sections, items = more_sections(window), set(more_actions(window))
        else:
            assert more_sections(window) == sections
            assert set(more_actions(window)) == items
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    assert window.planner.height() > window.height() * 0.8
    offered = more_actions(window)
    assert more_sections(window) == ["Adding", "Planning"]
    assert {"Add homework", "Add fixed time"} <= set(offered)
    assert {"Running late", "Routines", "Reload", "Undo", "Redo", "Advanced", "Log out"} <= set(offered)
    assert "Settings" not in offered
    assert "Account" not in offered
    assert (offered["Undo"], offered["Redo"]) == (True, False)


def test_a_more_item_does_what_its_button_does(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    before = len(window.session.blocks)
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    advanced = next(action.menu() for action in menu.actions() if action.text() == "Advanced")
    next(action for action in advanced.actions() if action.text() == "Undo").trigger()
    settled(qapp, window)
    assert len(window.session.blocks) != before or window.session.can_redo() is True


def test_day_and_month_follow_the_week_layout(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    click(window, "viewDay")
    assert type(window.planner.currentWidget()).__name__ == "BentoView"
    assert window.planner.currentWidget().scene.surface == "day"
    assert (window.solve_button.isVisible(), window.more_button.isVisible()) == (True, True)
    click(window, "viewMonth")
    settled(qapp, window)
    shown = window.planner.currentWidget()
    assert type(shown).__name__ == "BentoView"
    assert shown.scene.surface == "month"
    click(window, "viewWeek")
    assert (window.solve_button.isVisible(), window.more_button.isVisible()) == (True, True)
    click(window, "viewMyDay")
    assert type(window.planner.currentWidget()).__name__ == "OneThingView"
    assert (window.solve_button.isVisible(), window.more_button.isVisible()) == (True, True)


def test_todays_app_keeps_the_clock_day_and_chip_month(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_agenda
    assert window.solve_button.isVisible() is True
    click(window, "viewMonth")
    settled(qapp, window)
    assert window.planner.currentWidget() is window.month_grid


def test_bentos_buttons_reach_the_products_own_add_and_plan(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr(NativeWindow, "_add_homework", lambda self: asked.append("add"))
    monkeypatch.setattr(type(window.session), "solve", lambda self: asked.append("plan"))
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    click(window, "bentoAdd")
    click(window, "solveButton")
    click(window, "viewMyDay")
    assert asked == ["add", "plan"]
    assert type(window.planner.currentWidget()).__name__ == "OneThingView"


def test_every_layout_leaves_the_window_fitting_a_laptop(qapp: QApplication, window: NativeWindow) -> None:
    # A busy Thursday: with two blocks every view is short, and three designs only outgrew the screen
    # once the day had a realistic number of rows.
    for index, (title, start) in enumerate(
        (
            ("Soccer", "15:30"),
            ("Dinner", "18:00"),
            ("Chores", "17:15"),
            ("Reading", "20:00"),
            ("Club", "07:00"),
        )
    ):
        window.session.add_block(
            {"id": f"busy{index}", "title": title, "kind": "locked", "category": "extra",
             "start": start, "duration_min": 30, "days": [3]}
        )  # fmt: skip
    for index in range(3):
        window.session.add_homework(
            {"id": f"wait{index}", "title": f"Waiting {index}", "due": sunday_due(window.session.week_start),
             "estimate_min": 45, "revision": 0}
        )  # fmt: skip
    sizes = {}
    for layout_id, spec in LAYOUTS.items():
        if layout_id not in VIEW_CLASSES:
            continue
        window._day_mode = spec.role == "day"
        window._layout = {
            "main": layout_id if spec.role == "plan" else "classic",
            "day": "dial",
            "options": {},
        }
        if spec.role == "day":
            window._layout["day"] = layout_id
        window._on_week()
        qapp.processEvents()
        assert type(window.planner.currentWidget()).layout_id == layout_id
        sizes[layout_id] = (window.minimumSizeHint().width(), window.minimumSizeHint().height())
    assert {name: size for name, size in sizes.items() if size[0] > 1366 or size[1] > 768} == {}


def test_the_dialog_fits_a_laptop_with_every_level_open(qapp: QApplication) -> None:
    busiest = {
        "main": "timeline",
        "day": "dial",
        "options": {"timeline": {"finished": "hide"}, "dial": {"list": "hide"}},
    }
    dialog = prefs_layout(busiest)
    for name in ("layoutMainMore", "layoutDayMore"):
        assert dialog.findChild(QCheckBox, name).isChecked() is True
    dialog.show()
    qapp.processEvents()
    assert dialog.height() <= 768
    assert dialog.width() <= 1366
    assert dialog.sizeHint().height() <= 768
    assert dialog.sizeHint().width() <= 1366


def test_a_design_with_nothing_to_change_offers_no_fine_tune_or_reset(qapp: QApplication) -> None:
    dialog = prefs_layout()
    dialog.show()
    qapp.processEvents()

    def offered() -> tuple[bool, bool]:
        return (
            dialog.findChild(QCheckBox, "layoutMainMore").isVisible(),
            dialog.findChild(QPushButton, "layoutMainReset").isVisible(),
        )

    assert offered() == (False, False)
    pick = combo(dialog, "layoutMain")
    pick.setCurrentIndex(pick.findData("bento"))
    assert offered() == (True, True)
    pick.setCurrentIndex(pick.findData("classic"))
    assert offered() == (False, False)


def test_cancelling_settings_leaves_the_layout_alone(
    qapp: QApplication, window: NativeWindow
) -> None:
    before = dict(window._layout)

    def reject_after_bento(dialog: PrefsDialog) -> int:
        pick = dialog.findChild(QComboBox, "layoutMain")
        pick.setCurrentIndex(pick.findData("bento"))
        return QDialog.DialogCode.Rejected

    PrefsDialog.exec = reject_after_bento
    try:
        window._open_settings()
    finally:
        del PrefsDialog.exec
    assert window._layout == before
    assert type(window.planner.currentWidget()).__name__ != "BentoView"


def test_accepting_settings_applies_the_layout(qapp: QApplication, window: NativeWindow) -> None:
    def accept_bento(dialog: PrefsDialog) -> int:
        pick = dialog.findChild(QComboBox, "layoutMain")
        pick.setCurrentIndex(pick.findData("bento"))
        return QDialog.DialogCode.Accepted

    PrefsDialog.exec = accept_bento
    try:
        window._open_settings()
    finally:
        del PrefsDialog.exec
    settled(qapp, window)
    assert window._layout["main"] == "bento"
    assert type(window.planner.currentWidget()).__name__ == "BentoView"


def test_settings_fits_its_width_in_every_layout_and_text_size(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Settings scrolls down, never sideways. When a page was wider than its room the extra was cut
    off: every dropdown lost its arrow and the layout blurbs stopped mid-word. At large text the
    list beside it cut "Appearance & layout" short, and a group's title sat on its frame line over
    its first row. Measured in the real window, because the pack's padding and font are the cause."""
    choices = [{"main": main, "day": "one"} for main in LAYOUTS if LAYOUTS[main].role == "plan"]
    choices += [{"main": "classic", "day": day} for day in LAYOUTS if LAYOUTS[day].role == "day"]
    too_wide, cut_names, covered_titles = [], [], []
    for text in ("normal", "large"):
        window._look = {**window._look, "knobs": {**(window._look.get("knobs") or {}), "text": text}}
        window._apply_appearance()
        for choice in choices:
            dialog = PrefsDialog(
                window, window.session.preferences, window._look, window.session.reminder_limits, choice
            )
            dialog.show()
            for name in ("prefFineTune", "layoutMainMore", "layoutDayMore"):
                box = dialog.findChild(QCheckBox, name)
                if box is not None:
                    box.setChecked(True)
            settled(qapp, window)
            # Page by page, as a student opens them: a page that was never shown still has the
            # default font and reports a width it will not have once it is on screen.
            for index in range(dialog.stack.count()):
                dialog.nav.setCurrentRow(index)
                settled(qapp, window)
                area = dialog.stack.currentWidget()
                need, room = area.widget().minimumSizeHint().width(), area.viewport().width()
                if need > room or area.horizontalScrollBar().isVisible():
                    too_wide.append((text, choice["main"], choice["day"], index, need, room))
            dialog.nav.setCurrentRow(0)
            settled(qapp, window)
            if dialog.nav.sizeHintForColumn(0) > dialog.nav.viewport().width():
                cut_names.append((text, choice["main"], choice["day"]))
            for section in dialog.layout_sections:
                first = section.findChildren(QLabel)[0]
                if first.y() < section.fontMetrics().height():
                    covered_titles.append((text, section.slot, first.y()))
            dialog.close()
    assert too_wide == []
    assert cut_names == []
    assert covered_titles == []


def chrome_colour(window: NativeWindow) -> str:
    """What the top bar is actually painted with. A checked button blends, so this is only ever
    compared against another rendering, never against a token."""
    button = window.findChild(QPushButton, "signOut")
    return button.grab().toImage().pixelColor(button.width() // 2, button.height() // 2).name()


def chrome_accent(window: NativeWindow) -> str:
    from desktop.native.look import resolved_palette

    base = resolved_palette("light-frost", False, None, "default")
    return window._chrome_palette(base)["accent"]


def test_the_chrome_follows_whichever_design_is_on_screen(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    pack_accent, pack_pixels = chrome_accent(window), chrome_colour(window)

    for layout_id in ("bento", "mission", "clay"):
        window._layout = {"main": layout_id, "day": "one", "options": {}}
        window._on_week()
        qapp.processEvents()
        wanted = window.planner.currentWidget().scene.tokens["accent"]
        assert chrome_accent(window) == wanted, layout_id
        assert chrome_colour(window) != pack_pixels, layout_id

    window._layout = {"main": "classic", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    assert chrome_accent(window) == pack_accent
    assert chrome_colour(window) == pack_pixels


def test_a_day_screen_dresses_the_chrome_too(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    click(window, "viewMyDay")
    qapp.processEvents()
    assert chrome_accent(window) == window.planner.currentWidget().scene.tokens["accent"]


def test_category_colours_survive_a_layouts_colourway(qapp: QApplication, window: NativeWindow) -> None:
    """A block is School-blue in every design. Only the chrome follows the layout."""
    from desktop.native.layouts.registry import tokens_for
    from desktop.native.look import palette_from_tokens, resolved_palette

    base = resolved_palette("light-frost", False, None, "default")
    dressed = palette_from_tokens(tokens_for("bento", "sunset", base), base)
    assert dressed["window"] != base["window"]
    for key in ("block_locked", "block_flex", "block_edge"):
        assert dressed[key] == base[key], key


def test_no_chrome_button_spreads_across_the_window(qapp: QApplication, window: NativeWindow) -> None:
    """A button that fills the window reads as a banner, not a button. Seen at 439px on a day
    screen with focus running, and full width on the Day view."""
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    block = next(b for b in window.session.blocks if b.get("assignment_id"))
    window.session.start_focus(block["id"], 3)
    wait_until(qapp, lambda: window.session.focus is not None)
    qapp.processEvents()
    shown = [b for b in window.focus_panel.findChildren(QPushButton) if b.isVisible()]
    assert shown
    # "Not stretched" means each button is its own natural width, not a share of the window.
    stretched = [
        f"{b.objectName()} {b.width()}px vs {b.sizeHint().width()}px natural"
        for b in shown
        if b.width() > b.sizeHint().width() + 8
    ]
    assert stretched == []
    window.session.reset_focus()
    wait_until(qapp, lambda: window.session.focus is None)

    window._layout = {"main": "classic", "day": "one", "options": {}}
    click(window, "viewDay")
    qapp.processEvents()
    action = window.day_agenda.next_action
    assert action.isVisible()
    assert action.width() <= action.sizeHint().width() + 8, f"day action is {action.width()}px"


def test_every_dialog_fits_a_laptop_screen(qapp: QApplication, window: NativeWindow) -> None:
    """Settings stood 1056px tall and Account claimed 1338px wide. Both are opened on a 1366x768
    laptop, so both have to fit one."""
    from PySide6.QtWidgets import QDialog

    sizes: dict[str, tuple[int, int]] = {}
    original = QDialog.exec

    def measure(dialog: QDialog) -> int:
        dialog.show()
        qapp.processEvents()
        dialog.adjustSize()
        qapp.processEvents()
        sizes[measure.name] = (dialog.width(), dialog.height())
        dialog.hide()
        return QDialog.DialogCode.Rejected

    QDialog.exec = measure
    try:
        for name, call in (
            ("Settings", window._open_settings),
            ("Add homework", window._add_homework),
            ("Add fixed time", window._add_fixed),
            ("Account", window._open_account),
        ):
            measure.name = name
            call()
    finally:
        QDialog.exec = original
    assert sorted(sizes) == ["Account", "Add fixed time", "Add homework", "Settings"], sizes
    # A settings or account dialog is a panel, not a window. 1338x260 technically fitted a 1366
    # screen, which is why a screen-sized bound caught nothing; 700 square is the real rule.
    wrong = {name: size for name, size in sizes.items() if size[0] > 700 or size[1] > 768 or size[0] < 320}
    assert wrong == {}


def test_the_focus_timer_reads_as_one_status_line(qapp: QApplication, window: NativeWindow) -> None:
    """Over a design of its own the timer arrived as loose text: the homework, then the phase, then
    the countdown, each on its own row."""
    from PySide6.QtWidgets import QLabel

    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    block = next(b for b in window.session.blocks if b.get("assignment_id"))
    window.session.start_focus(block["id"], 3)
    wait_until(qapp, lambda: window.session.focus is not None)
    qapp.processEvents()
    parts = [window.focus_panel.findChild(QLabel, name) for name in ("focusTask", "focusPhase", "focusTime")]
    assert all(part is not None and part.isVisible() for part in parts)
    tops = {part.mapTo(window.focus_panel, part.rect().topLeft()).y() for part in parts}
    assert max(tops) - min(tops) < 8, f"the status is stacked, not one line: {sorted(tops)}"
    lefts = [part.mapTo(window.focus_panel, part.rect().topLeft()).x() for part in parts]
    assert lefts == sorted(lefts), "the parts should read left to right"
    window.session.reset_focus()
    wait_until(qapp, lambda: window.session.focus is None)


def test_a_real_solve_explains_itself_once(qapp: QApplication, window: NativeWindow) -> None:
    """Driven through the real solver, not a fixture trace. The panel opens when there is something
    to say, and a later week load must not reopen it."""
    # Ten hours due at the start of the week: there is no room before that deadline, so the solver
    # has something to say. Given a comfortable week it says nothing, which is the point of it.
    window.session.add_homework(
        {
            "id": "poster",
            "title": "Science fair poster",
            "due": f"{window.session.week_start}T08:00",
            "estimate_min": 600,
            "revision": 0,
        }
    )
    window.session.save()
    settled(qapp, window)
    window.session.solve()
    wait_until(qapp, lambda: window.session.trace is not None and not window.session.busy)
    qapp.processEvents()
    assert window.session.trace is not None
    said = [window.plan_review.list.item(i).text() for i in range(window.plan_review.list.count())]
    trace = window.session.trace
    assert trace.get("unplaced"), "the fixture should give the solver something it cannot place"
    assert said, "the solver had something to say and the panel showed nothing"
    assert any("Science fair poster" in line for line in said)
    assert window.plan_review.isVisible() is True

    # Reading the week again is not a new plan.
    window.plan_review.hide()
    window._on_week()
    qapp.processEvents()
    assert window.plan_review.isVisible() is False


def test_the_status_line_no_longer_swallows_the_explanation(qapp: QApplication, window: NativeWindow) -> None:
    window.session.solve()
    wait_until(qapp, lambda: not window.session.busy)
    qapp.processEvents()
    assert window.week_status.text().startswith("Placed ")


def test_the_week_toolbar_keeps_only_what_is_reached_for(qapp: QApplication, window: NativeWindow) -> None:
    """Twelve buttons competed for one row while nine more hid in an overflow menu, and a strip of
    eight category chips sat above them. The row keeps adding, planning, saving and starting a
    timer; everything else sits under the heading for its job.

    Retry save is not here: it appears only when a save has actually failed."""
    from PySide6.QtWidgets import QPushButton

    page = window._stack.currentWidget()
    shown = [
        button.objectName()
        for button in page.findChildren(QPushButton)
        if button.isVisible() and button.objectName()
    ]
    assert shown == [
        "prevWeek",
        "nextWeek",
        "viewDay",
        "viewWeek",
        "viewMonth",
        "viewMyDay",
        "solveButton",
        "moreButton",
        "settingsGear",
    ]

    menu = window.findChild(QPushButton, "moreButton").menu()
    menu.aboutToShow.emit()
    sections = [action.text() for action in menu.actions() if action.isSeparator() and action.text()]
    items = more_actions(window)
    assert sections == ["Adding", "Planning"]
    assert {"Undo", "Redo", "Duplicate", "Running late", "Routines", "Advanced", "Log out"} <= set(items)
    assert "Settings" not in items
    assert "Account" not in items


def test_the_gear_opens_settings(qapp: QApplication, window: NativeWindow) -> None:
    from PySide6.QtWidgets import QDialog

    gear = window.findChild(QPushButton, "settingsGear")
    assert gear is not None
    assert gear.text() == "⚙\uFE0E"
    assert gear.toolTip() == "Settings"
    assert gear.accessibleName() == "Settings"
    opened: list[str] = []
    original = QDialog.exec

    def measure(dialog: QDialog) -> int:
        opened.append(dialog.windowTitle())
        return QDialog.DialogCode.Rejected

    QDialog.exec = measure
    try:
        click(window, "settingsGear")
    finally:
        QDialog.exec = original
    assert opened == ["Settings"]


def test_more_hides_spotify_until_there_is_a_link(qapp: QApplication, window: NativeWindow) -> None:
    assert "Open Spotify link" not in more_actions(window)
    window.session.preferences = {
        **(window.session.preferences or {}),
        "default_spotify_url": SPOTIFY_TRACK,
    }
    assert "Open Spotify link" in more_actions(window)


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


def test_settings_holds_account_availability_and_updates(qapp: QApplication, window: NativeWindow) -> None:
    from desktop.native.settings import PrefsDialog
    from desktop.native.version import VERSION

    prefs = window.session.preferences or {}
    dialog = PrefsDialog(window, prefs, window._look, window.session.reminder_limits)
    assert dialog.findChild(QPushButton, "prefsAccount") is not None
    assert dialog.findChild(QPushButton, "prefsAvailability") is not None
    assert dialog.findChild(QLabel, "prefsVersion").text() == f"FlexWeek {VERSION}"
    assert dialog.findChild(QPushButton, "prefsCheckUpdates") is not None
    asked: list[str] = []
    dialog.account_requested.connect(lambda: asked.append("account"))
    dialog.availability_requested.connect(lambda: asked.append("availability"))
    dialog.updates_requested.connect(lambda: asked.append("updates"))
    dialog.findChild(QPushButton, "prefsAccount").click()
    dialog.findChild(QPushButton, "prefsAvailability").click()
    dialog.findChild(QPushButton, "prefsCheckUpdates").click()
    assert asked == ["account", "availability", "updates"]
    dialog.close()


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


class RingRecorder:
    """Stands in for the window's Bell so the ringing decision is visible without a sound card."""

    def __init__(self) -> None:
        self.started: list[tuple[str, object]] = []
        self.stops = 0
        self.ringing = False

    def start(self, tone: str, volume: object) -> bool:
        self.started.append((tone, volume))
        self.ringing = True
        return True

    def once(self, tone: str, volume: object) -> bool:
        self.started.append((tone, volume))
        return True

    def stop(self) -> None:
        self.stops += 1
        self.ringing = False


SPOTIFY_TRACK = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"


def no_spotify(monkeypatch: pytest.MonkeyPatch, opened: list) -> None:
    """Nothing in a test may hand a URL to the real desktop, which would open a browser."""
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        staticmethod(lambda url: bool(opened.append(url.toString())) or True),
    )


def test_an_alarm_rings_with_the_sound_it_was_given(qapp: QApplication, window: NativeWindow) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {**(window.session.preferences or {}), "alert_volume": 45}
    window._ring({"name": "Practice", "sound": "glass"}, "")
    assert window._bell.started == [("glass", 45)]


def test_an_alarm_set_to_spotify_plays_the_track_instead_of_a_tone(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list = []
    no_spotify(monkeypatch, opened)
    window._bell = RingRecorder()
    window._ring({"name": "Wake up", "sound": "spotify"}, SPOTIFY_TRACK)
    assert opened == [SPOTIFY_TRACK]
    assert window._bell.started == []


def test_a_spotify_alarm_with_no_link_still_makes_a_noise(qapp: QApplication, window: NativeWindow) -> None:
    """A best-effort link that is not there must not turn the alarm into a silent dialog."""
    window._bell = RingRecorder()
    window._ring({"name": "Wake up", "sound": "spotify"}, "")
    assert [tone for tone, _volume in window._bell.started] == ["chime"]


def test_a_spotify_alarm_falls_back_to_a_tone_when_the_link_will_not_open(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda _url: False))
    window._bell = RingRecorder()
    window._ring({"name": "Wake up", "sound": "spotify"}, SPOTIFY_TRACK)
    assert [tone for tone, _volume in window._bell.started] == ["chime"]


def test_answering_an_alarm_stops_the_noise(qapp: QApplication, window: NativeWindow) -> None:
    from PySide6.QtCore import QTimer

    window._bell = RingRecorder()
    QTimer.singleShot(0, lambda: window._alarm_dialog and window._alarm_dialog.accept())
    window._on_alarm({"id": "a1", "name": "Practice", "time": "07:00", "sound": "low"})
    assert [tone for tone, _volume in window._bell.started] == ["low"]
    assert window._bell.ringing is False
    assert window._bell.stops >= 1


def test_a_reminder_makes_its_sound_when_the_student_asked_for_one(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "alert_volume": 60,
    }
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    assert window._bell.started == [("chime", 60)]


def test_a_reminder_is_silent_when_the_student_turned_sound_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {**(window.session.preferences or {}), "reminder_sound": False}
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    assert window._bell.started == []


def test_the_end_of_session_chime_answers_to_its_own_setting(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The setting saved a value and played nothing. A focus notice is not a reminder: it uses the
    tone the phase carries and only sounds when the student asked for an end-of-session chime."""
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "end_chime": True,
        "alert_volume": 70,
    }
    window._present_alerts([{"title": "Focus session", "body": "Essay", "kind": "focus", "tone": "bright"}])
    assert window._bell.started == [("bright", 70)]


def test_no_chime_at_the_end_of_a_session_when_that_setting_is_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "end_chime": False,
    }
    window._present_alerts([{"title": "Break", "body": "Essay", "kind": "focus", "tone": "soft"}])
    assert window._bell.started == []


def test_a_reminder_still_rings_when_the_end_of_session_chime_is_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The two settings are separate, so gating one on the other would silence reminders."""
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "end_chime": False,
        "alert_volume": 80,
    }
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    assert window._bell.started == [("chime", 80)]


def test_open_on_day_is_honoured_instead_of_always_coming_up_on_the_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The setting could be saved from the desktop but only the web read it."""
    window._day_mode = False
    window._opened_on_preference = False
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "day"}
    window._on_week()
    qapp.processEvents()
    assert window._day_mode is True


def test_open_on_is_a_starting_point_not_a_lock(qapp: QApplication, window: NativeWindow) -> None:
    """Every week refresh runs through the same path, so applying it more than once would drag the
    student back to the day screen whenever the week reloaded."""
    window._day_mode = False
    window._opened_on_preference = False
    window.session.preferences = {**(window.session.preferences or {}), "preferred_view": "day"}
    window._on_week()
    qapp.processEvents()
    window._leave_day()
    qapp.processEvents()
    assert window._day_mode is False
    window._on_week()
    qapp.processEvents()
    assert window._day_mode is False


def menu_swatches(window: NativeWindow) -> dict:
    """The colour beside each type in the Add menu, read back off its icon."""
    from PySide6.QtGui import QAction

    from desktop.native.calendar import CATEGORIES

    faces = {}
    for key in CATEGORIES:
        action = window.add_menu.findChild(QAction, f"addMenu-{key}")
        assert action is not None, key
        image = action.icon().pixmap(12, 12).toImage()
        faces[key] = image.pixelColor(6, 6).name()
    return faces


def test_the_add_menu_says_which_type_each_entry_makes(qapp: QApplication, window: NativeWindow) -> None:
    """The chip strip carried the category colours and took a whole row to do it. The colours moved
    into the Add menu with it."""
    from desktop.native.calendar import CATEGORIES

    window.session.preferences = {**(window.session.preferences or {}), "accent_chips": False}
    window._on_week()
    qapp.processEvents()
    assert len(set(menu_swatches(window).values())) == len(CATEGORIES)


def test_accent_chips_paints_every_type_in_the_accent(qapp: QApplication, window: NativeWindow) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "accent_chips": True}
    window._on_week()
    qapp.processEvents()
    assert len(set(menu_swatches(window).values())) == 1


def test_day_and_month_wear_the_same_design_as_the_week(qapp: QApplication, window: NativeWindow) -> None:
    """The design used to be read off whichever widget was on screen, so it dressed the week and
    nothing else: pressing Day or Month dropped back to the pack's own blue and the app looked like
    two programs. A layout is a whole way of showing a week, not a skin for one page of it."""
    from desktop.native.look import resolved_palette

    window._layout = sanitize_layout({"main": "bento", "day": "one"})
    window._day_mode = False
    pack, system_dark, accent = window._look_inputs()
    plain = resolved_palette(pack, system_dark, window._look, accent)
    seen = {}
    for view in ("week", "day", "month"):
        window.session.set_view(view)
        qapp.processEvents()
        seen[view] = window._chrome_palette(plain)["accent"]
    assert len(set(seen.values())) == 1, seen
    assert seen["week"] != plain["accent"], "the design never took effect at all"


def test_classic_keeps_the_pack_it_is_made_of(qapp: QApplication, window: NativeWindow) -> None:
    """Classic is the app's own look, so there is no design palette to derive."""
    from desktop.native.look import resolved_palette

    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._day_mode = False
    pack, system_dark, accent = window._look_inputs()
    plain = resolved_palette(pack, system_dark, window._look, accent)
    assert window._chrome_palette(plain) == plain


def test_the_day_screen_brings_its_own_design_with_it(qapp: QApplication, window: NativeWindow) -> None:
    """My day picks a design of its own, and that one wins while it is showing."""
    from desktop.native.look import resolved_palette

    window._layout = sanitize_layout({"main": "bento", "day": "dial"})
    pack, system_dark, accent = window._look_inputs()
    plain = resolved_palette(pack, system_dark, window._look, accent)
    window._day_mode = False
    planning = window._chrome_palette(plain)["accent"]
    window._day_mode = True
    watching = window._chrome_palette(plain)["accent"]
    assert planning != watching


class FakeUpdater:
    """Stands in for the real one so no test reaches the network."""

    def __init__(self) -> None:
        self.checks = 0
        self.downloads: list[dict] = []
        self.busy = False

    def check(self) -> None:
        self.checks += 1

    def download(self, update: dict) -> None:
        self.downloads.append(update)


def test_the_app_checks_for_updates_once_a_day_not_every_week_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    """_on_week runs on every save, solve and week change. Checking there without a cadence would
    ask GitHub dozens of times a session."""
    fake = FakeUpdater()
    window._updater = fake
    window._updates = {"check": True, "last_ms": 0, "skip": ""}
    window._on_week()
    qapp.processEvents()
    assert fake.checks == 1
    window._on_week()
    window._on_week()
    qapp.processEvents()
    assert fake.checks == 1, "a week refresh asked GitHub again"


def test_turning_update_checks_off_is_obeyed(qapp: QApplication, window: NativeWindow) -> None:
    fake = FakeUpdater()
    window._updater = fake
    window._updates = {"check": False, "last_ms": 0, "skip": ""}
    window._on_week()
    qapp.processEvents()
    assert fake.checks == 0


def test_asking_for_a_check_ignores_the_cadence(qapp: QApplication, window: NativeWindow) -> None:
    """Check for updates has to check, whatever the daily timer says."""
    fake = FakeUpdater()
    window._updater = fake
    window._updates = {"check": True, "last_ms": window.session.now_ms(), "skip": ""}
    window._check_updates(asked=True)
    assert fake.checks == 1


def test_a_skipped_version_stays_quiet_until_asked(qapp: QApplication, window: NativeWindow) -> None:
    window._updates = {"check": True, "last_ms": 0, "skip": "9.9.9"}
    window._update_asked = False
    shown: list = []
    window._on_update_found({"version": "9.9.9", "asset": "x", "url": "u", "checksum_url": "c", "notes": ""})
    assert shown == []
    assert window._update_dialog is None


def test_no_button_appears_twice_on_the_week_page(qapp: QApplication, window: NativeWindow) -> None:
    """Moving Quick focus into the action row left the focus panel's own copy on screen, so the same
    button was offered twice a few pixels apart. The action row is not the only place a button can
    come from, so this counts them across the whole page rather than inside one container."""
    from PySide6.QtWidgets import QPushButton

    window._day_mode = False
    window._on_week()
    qapp.processEvents()
    page = window._stack.currentWidget()
    labels = [b.text() for b in page.findChildren(QPushButton) if b.isVisible() and b.text()]
    repeated = sorted({text for text in labels if labels.count(text) > 1})
    assert repeated == [], f"offered twice: {repeated}"


def test_the_add_button_says_what_a_drag_will_make(qapp: QApplication, window: NativeWindow) -> None:
    """The armed type was legible because eight chips sat on screen with one of them lit. With the
    chips gone, the button that opens the menu has to carry it."""
    from PySide6.QtWidgets import QPushButton

    # arm_category, not _add_from_chip: that one also opens the Add dialog, which blocks.
    window.session.arm_category("exercise")
    window._sync_add_button()
    qapp.processEvents()
    button = window.findChild(QPushButton, "addButton")
    assert button is not None
    assert "sport" in button.text().lower()
    assert not button.icon().isNull(), "no colour beside the armed type"


def test_the_week_saves_itself_without_anyone_pressing_save(qapp: QApplication, window: NativeWindow) -> None:
    """Save left the bar, so this is the only thing that writes a student's week. If it stops
    working, work is lost silently, which is the worst failure this app has."""
    from desktop.native.calendar import sunday_due

    before = window.session.revision
    window.session.add_homework(
        {
            "id": "auto",
            "title": "Autosaved essay",
            "due": sunday_due(window.session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    assert window.session.dirty is True
    # The clock the debounce reads is the session's, so move it rather than sleeping.
    window._changed_ms = 0
    window._last_try_ms = 0
    window._autosave_tick()
    wait_until(qapp, lambda: not window.session.busy and window.session.revision > before)
    assert window.session.dirty is False


def test_autosave_waits_until_the_student_stops_changing_things(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Dragging a block emits a change per step. Saving on each one would post continuously."""
    window.session.dirty = True
    window.session.pending_save = None
    window._changed_ms = window.session.now_ms()
    posted = []
    window.session.save = lambda *a, **k: posted.append(1)
    window._autosave_tick()
    assert posted == [], "saved while the student was still changing things"


def test_autosave_keeps_its_hands_off_a_conflict(qapp: QApplication, window: NativeWindow) -> None:
    """A 409 means another window wrote this week. Answering that is the student's decision, and a
    timer that retried would overwrite whichever copy lost the race."""
    window.session.dirty = True
    window.session.conflict = True
    window._changed_ms = 0
    posted = []
    window.session.save = lambda *a, **k: posted.append(1)
    window._autosave_tick()
    assert posted == []


def test_autosave_does_not_pile_requests_on_a_busy_session(qapp: QApplication, window: NativeWindow) -> None:
    window.session.dirty = True
    window.session.conflict = False
    window.session.busy = True
    window._changed_ms = 0
    posted = []
    window.session.save = lambda *a, **k: posted.append(1)
    window._autosave_tick()
    window.session.busy = False
    assert posted == []
