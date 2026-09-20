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
    from desktop.native.layouts.registry import LAYOUTS, sanitize_layout
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
    assert window.plan_chrome.isVisible() is True
    QTest.keyClick(window.month_grid.table, Qt.Key.Key_T)
    assert isinstance(window.planner.currentWidget(), OneThingView)


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


def tool_actions(window: NativeWindow) -> dict[str, bool]:
    """The items, without the section headings. addSection makes a separator that carries text."""
    menu = window.tools_button.menu()
    menu.aboutToShow.emit()
    return {
        action.text(): action.isEnabled()
        for action in menu.actions()
        if action.text() and not action.isSeparator()
    }


def tool_sections(window: NativeWindow) -> list[str]:
    menu = window.tools_button.menu()
    menu.aboutToShow.emit()
    return [action.text() for action in menu.actions() if action.isSeparator() and action.text()]


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
    # Grouped by the job each action does, rather than one flat list of twenty.
    assert tool_sections(window) == ["Adding", "Planning", "Editing", "Your week", "Account"]
    offered = tool_actions(window)
    assert list(offered)[:3] == ["Add homework", "Add fixed time", "Plan my homework"]
    assert {"Settings", "Running late", "Routines", "Account", "Reload", "Undo", "Redo"} <= set(offered)
    assert (offered["Undo"], offered["Redo"]) == (True, False)


def test_a_tool_does_what_its_button_does(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    before = len(window.session.blocks)
    menu = window.tools_button.menu()
    next(action for action in menu.actions() if action.text() == "Undo").trigger()
    settled(qapp, window)
    assert len(window.session.blocks) != before or window.session.can_redo() is True


def test_day_and_month_follow_the_week_layout(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "bento", "day": "one", "options": {}}
    click(window, "viewDay")
    assert type(window.planner.currentWidget()).__name__ == "BentoView"
    assert window.planner.currentWidget().scene.surface == "day"
    assert (window.plan_chrome.isVisible(), window.tools_button.isVisible()) == (False, True)
    click(window, "viewMonth")
    settled(qapp, window)
    shown = window.planner.currentWidget()
    assert type(shown).__name__ == "BentoView"
    assert shown.scene.surface == "month"
    click(window, "viewWeek")
    assert (window.plan_chrome.isVisible(), window.tools_button.isVisible()) == (False, True)
    click(window, "viewMyDay")
    assert type(window.planner.currentWidget()).__name__ == "OneThingView"
    assert (window.plan_chrome.isVisible(), window.tools_button.isVisible()) == (False, False)


def test_todays_app_keeps_the_clock_day_and_chip_month(qapp: QApplication, window: NativeWindow) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    click(window, "viewDay")
    assert window.planner.currentWidget() is window.day_agenda
    assert window.plan_chrome.isVisible() is True
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
    click(window, "bentoPlan")
    click(window, "bentoMyDay")
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
    dialog = LayoutDialog(None, busiest)
    for name in ("layoutMainMore", "layoutDayMore"):
        assert dialog.findChild(QCheckBox, name).isChecked() is True
    dialog.show()
    qapp.processEvents()
    assert dialog.sizeHint().height() <= 700
    assert dialog.sizeHint().width() <= 1300


def test_a_design_with_nothing_to_change_offers_no_fine_tune_or_reset(qapp: QApplication) -> None:
    dialog = LayoutDialog(None, None)
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
    """Twelve buttons competed for one row while nine more hid in an overflow menu. The row keeps
    adding, planning and saving; everything else sits under the heading for its job."""
    from PySide6.QtWidgets import QPushButton

    # The action row, not the category chips that sit above it.
    shown = [
        button.objectName()
        for button in window.plan_chrome.findChildren(QPushButton)
        if button.isVisible() and button.objectName() and not button.objectName().startswith("chip-")
    ]
    assert shown == ["addHomework", "addFixed", "solveButton", "saveButton", "retrySave", "moreButton"]

    menu = window.findChild(QPushButton, "moreButton").menu()
    menu.aboutToShow.emit()
    sections = [action.text() for action in menu.actions() if action.isSeparator() and action.text()]
    items = {action.text() for action in menu.actions() if action.text() and not action.isSeparator()}
    assert sections == ["Planning", "Editing", "Your week", "Account"]
    assert {"Undo", "Redo", "Duplicate", "Running late", "Routines", "Account", "Settings"} <= items


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


def chip_faces(window: NativeWindow) -> dict:
    """The colour each chip wears when it is the armed one."""
    from desktop.native.calendar import CATEGORIES

    faces = {}
    for key in CATEGORIES:
        button = window.chips.findChild(QPushButton, f"chip-{key}")
        assert button is not None, key
        checked = [part for part in button.styleSheet().split("}") if ":checked" in part]
        assert checked, key
        faces[key] = checked[0].split("background:")[1].split(";")[0].strip()
    return faces


def test_the_chips_say_which_category_they_arm(qapp: QApplication, window: NativeWindow) -> None:
    """They carried no colour at all, so nothing tied a chip to the blocks it makes."""
    from desktop.native.calendar import CATEGORIES

    window.session.preferences = {**(window.session.preferences or {}), "accent_chips": False}
    window._on_week()
    qapp.processEvents()
    faces = chip_faces(window)
    assert len(set(faces.values())) == len(CATEGORIES)


def test_accent_chips_paints_them_all_in_the_accent(qapp: QApplication, window: NativeWindow) -> None:
    """The setting was saved and never read here; the web has painted its chips this way all along."""
    window.session.preferences = {**(window.session.preferences or {}), "accent_chips": True}
    window._on_week()
    qapp.processEvents()
    assert len(set(chip_faces(window).values())) == 1


def test_saving_start_at_login_changes_this_machine_not_just_the_account(
    qapp: QApplication, window: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The preference synced to the account and no machine ever acted on it."""
    from desktop.native import autostart

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    entry = tmp_path / "autostart" / autostart.ENTRY_NAME
    window._apply_start_at_login(True)
    assert entry.exists()
    window._apply_start_at_login(False)
    assert not entry.exists()


def test_alerts_stay_on_screen_when_the_student_asked_them_to(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A tray message is gone in eight seconds and a machine may suppress it entirely. The setting
    saved a value and nothing anywhere acted on it."""
    window.session.preferences = {**(window.session.preferences or {}), "reminder_dnd_override": True}
    window.alert_strip.clear()
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    qapp.processEvents()
    assert window.alert_strip.isVisible() is True
    assert "Essay starts soon" in window.alert_strip.text.text()


def test_alerts_do_not_pile_up_in_the_window_when_it_is_off(qapp: QApplication, window: NativeWindow) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "reminder_dnd_override": False}
    window.alert_strip.clear()
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    qapp.processEvents()
    assert window.alert_strip.isVisible() is False


def test_dismissing_one_alert_reveals_the_next_rather_than_losing_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.preferences = {**(window.session.preferences or {}), "reminder_dnd_override": True}
    window.alert_strip.clear()
    window._present_alerts([{"title": "First", "body": "a"}, {"title": "Second", "body": "b"}])
    qapp.processEvents()
    assert "First" in window.alert_strip.text.text()
    assert "+1 more" in window.alert_strip.text.text()
    window.alert_strip.dismiss.click()
    qapp.processEvents()
    assert "Second" in window.alert_strip.text.text()
    window.alert_strip.dismiss.click()
    qapp.processEvents()
    assert window.alert_strip.isVisible() is False


def test_a_field_keeps_its_floor_at_every_text_size(qapp: QApplication) -> None:
    """The Layout dialog came up a few pixels under its natural height on a real KDE desktop and the
    rows were squeezed until "Colours" and "Soft" were slivers of their letters. A combo box has no
    useful minimum of its own there, so the floor comes from the look.

    Asserted on the stylesheet rather than on a live widget: the offscreen platform this runs on
    gives a combo box a generous native minimum, so a widget-level check passes with or without the
    fix and would prove nothing."""
    from desktop.native.look import FIELD_MIN_PX, pack_stylesheet

    for size in ("small", "normal", "large"):
        sheet = pack_stylesheet("light-frost", False, {"preset": "default", "knobs": {"text": size}})
        # The floor has to be on the field rule itself. Menu items carry a min-height of their own,
        # so looking for the number anywhere in the sheet would pass without the fields having one.
        rule = next(part for part in sheet.split("}") if part.lstrip().startswith("QLineEdit"))
        assert f"min-height: {FIELD_MIN_PX[size]}px" in rule, (size, rule)


def test_the_way_in_is_signing_in_not_a_choice_between_two_buttons(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Create account and Sign in sat side by side as equals, so every arrival had to choose before
    reading anything. A student creates an account once and signs in from then on."""
    window._making_account = False
    window._sync_auth_mode()
    qapp.processEvents()
    assert window.auth_heading.text() == "Sign in"
    # isHidden, not isVisible: the fixture is signed in, so every child of the auth page reports
    # not visible whatever mode it is in.
    assert window.sign_in_button.isHidden() is False
    assert window.create_button.isHidden() is True
    assert "Create an account" in window.auth_switch.text()


def test_the_small_print_switches_to_making_an_account_and_back(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._making_account = False
    window._sync_auth_mode()
    window.auth_switch.click()
    qapp.processEvents()
    assert window.auth_heading.text() == "Create your account"
    assert window.create_button.isHidden() is False
    assert window.sign_in_button.isHidden() is True
    assert "Sign in" in window.auth_switch.text()
    window.auth_switch.click()
    qapp.processEvents()
    assert window.auth_heading.text() == "Sign in"


def test_pressing_return_does_the_thing_the_screen_is_for(qapp: QApplication, window: NativeWindow) -> None:
    """Whichever mode is showing, its own button is the default, so Return never does the other one."""
    window._making_account = False
    window._sync_auth_mode()
    assert window.sign_in_button.isDefault() is True
    window._making_account = True
    window._sync_auth_mode()
    assert window.create_button.isDefault() is True


def test_signing_out_comes_back_to_the_sign_in_screen(qapp: QApplication, window: NativeWindow) -> None:
    window._making_account = True
    window._sync_auth_mode()
    window._on_account(None)
    qapp.processEvents()
    assert window._making_account is False
    assert window.auth_heading.text() == "Sign in"


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
