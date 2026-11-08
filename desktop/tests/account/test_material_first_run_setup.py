"""Material first-run setup, in the real window against the real backend in this process: each step in
order, what was answered and kept, where the window goes when setup ends, and keyboard focus staying on
the visible Material controls.

Expected words and values come from the Widgets setup and the requirement, not from reading the QML.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication

from desktop.native.setup import COLOURS, DONE, FIRST, HOMEWORK, LOOK, REMINDERS, STYLE, WEEK
from desktop.tests.account.support import (
    LightLaunches,
    account,
    create,
    material_launches,  # noqa: F401
    page,
    qml,
    settle,
    shown,
    sign_out,
    skip_setup,
    through_recovery,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def test_setup_keeps_each_step_in_order_and_what_was_answered(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "setup_student")
    through_recovery(qapp, window)
    session = window.session
    # The style step offers Material 3 first, then the four standard styles.
    keys = [row["key"] for row in bridge.styles]
    assert keys[0] == "material"
    assert len(keys) == 5
    assert [row["selected"] for row in bridge.styles][0] is True
    seen = [bridge.setupStep]

    def step_saved(step: int) -> bool:
        wanted = (session.preferences or {}).get("setup", {}).get("step")
        return wanted == step

    # Style -> Your week
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(WEEK))
    bridge.setClock24(True)
    bridge.setCutoff("21:00")
    bridge.toggleSchoolDay(5)
    assert 5 in bridge.schoolDays
    bridge.toggleSchoolDay(5)
    bridge.setActivityTitle(0, "Soccer")
    bridge.toggleActivityDay(0, 1)
    bridge.toggleActivityDay(0, 3)
    bridge.setActivityStart(0, "4:00 pm")
    bridge.setActivityEnd(0, "17:30")
    assert bridge.activities[0]["category"] == "exercise"
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(HOMEWORK))
    assert session.preferences["day_cutoff"] == "21:00"
    assert session.preferences["clock_24h"] is True
    soccer = next(block for block in session.blocks if block["title"] == "Soccer")
    assert soccer["days"] == [1, 3] and soccer["start"] == "16:00" and soccer["duration_min"] == 90
    # Homework time
    bridge.setPlanning("manual")
    bridge.setDragStep(15)
    bridge.addWorkPreset("After school")
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(REMINDERS))
    assert session.preferences["planning_style"] == "manual"
    assert session.preferences["drag_step_min"] == 15
    settle(qapp, window)
    assert session.preferences["work_windows"][0]["start"] == "15:30"
    # Reminders
    bridge.setReminders(True)
    bridge.setLead(20)
    tone = next(row["value"] for row in bridge.tones if row["value"] != "spotify")
    bridge.setTone(tone)
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(FIRST))
    assert session.preferences["reminder_lead_min"] == 20
    assert session.preferences["alarm_tone"] == tone
    # First homework
    bridge.setHomeworkTitle(0, "Chemistry lab")
    bridge.setHomeworkMinutes(0, 45)
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(DONE))
    assert seen == [STYLE, WEEK, HOMEWORK, REMINDERS, FIRST, DONE]
    assert any(item["title"] == "Chemistry lab" for item in session.assignments.values())
    assert "Chemistry lab" in " ".join(row["value"] for row in bridge.summaryRows)
    assert bridge.summaryRows[0]["value"] == "Material 3"
    assert bridge.nextLabel == "Open my week"
    # Finish: the Material week opens.
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    assert page(window) == "materialPage"
    assert shown(window, "materialRail")
    assert (session.preferences.get("setup") or {}).get("finished_at")
    assert window._surface == "material"


def test_picking_a_standard_style_hands_the_window_to_widgets_when_setup_ends(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "plain_student")
    through_recovery(qapp, window)
    plain = next(row["key"] for row in bridge.styles if row["key"] != "material")
    bridge.chooseStyle(plain)
    bridge.setupNext()
    assert window._surface == "material"  # not yet: setup is still on screen
    bridge.setupSkipAll()
    wait_until(qapp, lambda: window._surface == "widgets")
    settle(qapp, window)
    assert page(window) == "weekPage"
    assert json.loads(look_file().read_text())["surface"] == "widgets"


def test_a_second_account_does_not_inherit_the_first_ones_answers(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "first_student")
    through_recovery(qapp, window)
    bridge.setupNext()
    bridge.setCutoff("20:00")
    bridge.setActivityTitle(0, "Robotics club")
    bridge.toggleActivityDay(0, 2)
    bridge.setupNext()
    bridge.setupNext()
    bridge.setupNext()
    bridge.setHomeworkTitle(0, "Essay for first")
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == DONE)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    sign_out(qapp, window)
    assert bridge.username == "" and bridge.password == ""
    create(qapp, window, "second_student")
    through_recovery(qapp, window)
    assert bridge.setupStep == STYLE
    assert [row["selected"] for row in bridge.styles][0] is True
    bridge.setupNext()
    assert bridge.setupStep == WEEK
    assert bridge.cutoff == ""
    assert bridge.activities == [
        {"title": "", "days": [], "start": "3:30 PM", "end": "5:00 PM", "category": "extra"}
    ]
    for _ in range(3):
        bridge.setupNext()
    assert bridge.setupStep == FIRST
    assert [row["title"] for row in bridge.homeworkRows] == [""]
    assert not any(block["title"] == "Robotics club" for block in window.session.blocks)


def test_a_time_that_ends_before_it_starts_stops_the_week_step(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "clock_student")
    through_recovery(qapp, window)
    bridge.setupNext()
    bridge.setSchoolStart("2:00 pm")
    bridge.setSchoolEnd("8:00 am")
    bridge.setupNext()
    assert bridge.setupStep == WEEK
    assert bridge.setupProblem == "School has to end after it starts."
    problem = "School has to end after it starts."
    wait_until(qapp, lambda: qml(window, "setupProblem").property("text") == problem)
    bridge.setSchoolEnd("4:00 pm")
    bridge.setupNext()
    assert bridge.setupStep == HOMEWORK


def test_an_own_look_adds_the_look_and_colour_pages(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "look_student")
    through_recovery(qapp, window)
    bridge.chooseOwnLook()
    assert bridge.setupStep == LOOK
    assert len(bridge.mains) >= 2
    bridge.setupNext()
    assert bridge.setupStep == COLOURS
    assert [row["key"] for row in bridge.knobRows][:2] == ["text", "density"]
    bridge.setupBack()
    assert bridge.setupStep == LOOK


def test_setup_keeps_the_computers_material_mode(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    look_file().write_text(json.dumps({"surface": "material", "material": {"mode": "dark"}}) + "\n")
    window = material_launches.launch()
    create(qapp, window, "dark_mode_student")
    through_recovery(qapp, window)
    skip_setup(qapp, window)
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored["material"]["mode"] == "dark"
    assert account(window).phase == "app"
    assert window._material_page.bridge.dark is True


def test_graphics_fallback_during_material_setup_keeps_the_widgets_step(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    """A scene-graph failure mid-setup must finish from the Widgets page, not the abandoned bridge."""
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "fallback_setup_student")
    through_recovery(qapp, window)
    assert bridge.phase == "setup"
    assert bridge.setupStep == STYLE
    assert page(window) == "materialPage"
    bridge._surface_pick = "widgets"

    window._give_up_material(show_week=False)
    wait_until(qapp, lambda: page(window) == "setupPage")
    assert window._material_gave_up is True
    assert window.setup_page.step == STYLE
    assert bridge.phase == "app"

    window.setup_page.next.click()
    wait_until(qapp, lambda: window.setup_page.step == WEEK)
    widgets_step = window.setup_page.step
    window.setup_page.skip_all.click()
    wait_until(qapp, lambda: bool((window.session.preferences or {}).get("setup", {}).get("finished_at")))
    settle(qapp, window)

    progress = window.session.preferences["setup"]
    assert progress["step"] == widgets_step
    assert window._surface == "material"
    assert json.loads(look_file().read_text())["surface"] == "material"
    assert bridge._surface_pick == "widgets"


def test_setup_focus_and_tab_ownership_stays_on_visible_material_controls(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "focus_student")
    through_recovery(qapp, window)

    # Surface and phase
    assert page(window) == "materialPage"
    assert bridge.phase == "setup"
    assert shown(window, "setupFlow")
    assert bridge.setupStep == STYLE

    # Widgets setup must NOT be opened underneath Material setup
    assert window.setup_page.carousel.hasFocus() is False
    assert window.setup_page.isVisible() is False

    # Window focus ownership: Material quick surface owns keyboard focus; Widgets setup is not opened
    quick = window.findChild(QQuickWidget, "materialQuick")
    assert quick is not None
    assert window.focusWidget() is quick

    # Active focus item in Quick scene belongs to Material setup
    qw = quick.quickWindow()
    assert qw is not None
    assert qw.activeFocusItem() is not None

    # Tab navigation visits visible Material setup controls in order and remains inside Material quick surface
    tabbed_names: list[str] = []
    for _ in range(16):
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        qapp.sendEvent(quick, ev)
        item = qw.activeFocusItem()
        assert item is not None
        assert window.focusWidget() is quick
        assert window.setup_page.carousel.hasFocus() is False
        tabbed_names.append(item.property("objectName") or "")

    # Visible step rail, choice cards, and footer buttons are in the tab sequence
    assert "setupStep0" in tabbed_names
    assert "setupStyle-material" in tabbed_names
    assert "setupNext" in tabbed_names

    # Shift+Tab reverses focus and never escapes to hidden Widgets setup
    for _ in range(16):
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        qapp.sendEvent(quick, ev)
        item = qw.activeFocusItem()
        assert item is not None
        assert window.focusWidget() is quick
        assert window.setup_page.carousel.hasFocus() is False
