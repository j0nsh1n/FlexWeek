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
    labels = list(offered)
    assert labels[:6] == ["Add fixed time", "Add homework", "Plan my homework", "Undo", "Redo", "Copy"]
    assert labels[7:10] == ["Duplicate", "Save", "Retry save"]
    assert labels[6].startswith("Paste")
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

    click(window, "viewDay")
    qapp.processEvents()
    action = window.day_agenda.next_action
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
