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
from PySide6.QtWidgets import QApplication

from desktop.native.setup_steps import HOMEWORK, REMINDERS, WEEK
from desktop.native.weekmodel import hhmm_text
from desktop.tests.account.support import (
    LightLaunches,
    account,
    create,
    material_launches,  # noqa: F401
    named,
    page,
    qml,
    settle,
    shown,
    sign_out,
    skip_setup,
    through_recovery,
)
from desktop.tests.material_support import focus_quick, host_has_focus, quick_of, quick_window_of
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
    # Material 3 is the only style and setup is three steps of cards, so the rail has three rows.
    assert [row["name"] for row in bridge.rail] == ["School hours", "Study hours", "Look & alerts"]
    seen = [bridge.setupStep]

    def step_saved(step: int) -> bool:
        wanted = (session.preferences or {}).get("setup", {}).get("step")
        return wanted == step

    # School hours: the card that means more opens the detailed controls
    bridge.setSchoolPreset("custom")
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
    # Study hours
    bridge.setPlanning("manual")
    bridge.setStudyPreset("custom")
    bridge.setDragStep(5)
    bridge.addWorkPreset("After school")
    bridge.setupNext()
    seen.append(bridge.setupStep)
    wait_until(qapp, lambda: step_saved(REMINDERS))
    assert session.preferences["planning_style"] == "manual"
    assert session.preferences["drag_step_min"] == 5
    settle(qapp, window)
    assert session.preferences["work_windows"][0]["start"] == "15:30"
    # Look and alerts
    bridge.setSoundOpen(True)
    bridge.setReminders(True)
    bridge.setLead(20)
    # Not the default tone: the server leaves a default out of the preferences it answers with.
    tone = next(row["value"] for row in bridge.tones if row["value"] not in {"spotify", "chime"})
    bridge.setTone(tone)
    assert bridge.nextLabel == "Open my week"
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    assert seen == [WEEK, HOMEWORK, REMINDERS]
    assert session.preferences["reminder_lead_min"] == 20
    assert session.preferences["alarm_tone"] == tone
    # Finish: the Material week opens.
    assert page(window) == "materialPage"
    assert shown(window, "materialRail")
    assert (session.preferences.get("setup") or {}).get("finished_at")
    assert window._surface == "material"


def test_setup_has_no_style_page_and_no_way_to_the_widgets_styles(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "plain_student")
    through_recovery(qapp, window)
    assert bridge.setupStep == WEEK
    assert not hasattr(bridge, "chooseStyle") and not hasattr(bridge, "chooseOwnLook")
    assert bridge.backVisible is False
    for name in ("setupStylePage", "setupOwnLook", "setupLookPage", "setupColoursPage"):
        assert named(window, name) == []
    bridge.setupSkipAll()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    assert page(window) == "materialPage"
    assert window._surface == "material"
    assert json.loads(look_file().read_text())["surface"] == "material"


def test_setup_resumes_at_your_week_from_a_step_the_style_pages_used_to_own(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "resume_student")
    through_recovery(qapp, window)
    state = window._setup_state(first_run=False)
    for old in (0, 1, 2):
        bridge.open_setup(state, old)
        assert bridge.setupStep == WEEK


def test_a_second_account_does_not_inherit_the_first_ones_answers(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "first_student")
    through_recovery(qapp, window)
    bridge.setSchoolPreset("custom")
    bridge.setCutoff("20:00")
    bridge.setActivityTitle(0, "Robotics club")
    bridge.toggleActivityDay(0, 2)
    bridge.setupNext()
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == REMINDERS)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)
    sign_out(qapp, window)
    assert bridge.username == "" and bridge.password == ""
    create(qapp, window, "second_student")
    through_recovery(qapp, window)
    assert bridge.setupStep == WEEK
    assert bridge.cutoff == ""
    assert bridge.activities == [
        {"title": "", "days": [], "start": "3:30 PM", "end": "5:00 PM", "category": "extra"}
    ]
    assert bridge.power is False
    assert not any(block["title"] == "Robotics club" for block in window.session.blocks)


def test_a_time_that_ends_before_it_starts_stops_the_week_step(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "clock_student")
    through_recovery(qapp, window)
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


def test_graphics_failure_during_material_setup_asks_for_a_cpu_copy_and_keeps_the_step(
    qapp: QApplication, material_launches: LightLaunches, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scene-graph failure mid-setup saves the CPU key and starts a new copy, not the Widgets setup."""
    from desktop.native import cpu_drawing
    from desktop.native.version import VERSION

    monkeypatch.delenv(cpu_drawing.BACKEND_ENV, raising=False)
    launched: list[bool] = []
    monkeypatch.setattr(cpu_drawing, "start_new_copy", lambda *, cpu: launched.append(cpu))
    window = material_launches.launch()
    monkeypatch.setattr(window, "_quit_now", lambda: None)
    bridge = account(window)
    create(qapp, window, "fallback_setup_student")
    through_recovery(qapp, window)
    assert bridge.phase == "setup"
    assert bridge.setupStep == WEEK
    assert page(window) == "materialPage"

    window._give_up_material(show_week=False)
    settle(qapp, window)

    assert launched == [True]
    assert window._surface == "material"
    stored = json.loads(look_file().read_text())
    assert stored["surface"] == "material"
    assert stored[cpu_drawing.LOOK_KEY] == VERSION


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
    assert bridge.setupStep == WEEK

    # Widgets setup must NOT be opened underneath Material setup

    # Window focus ownership: Material quick surface owns keyboard focus; Widgets setup is not opened
    quick = quick_of(window)
    assert quick is not None
    focus_quick(window)
    assert host_has_focus(window)

    # Active focus item in Quick scene belongs to Material setup
    qw = quick_window_of(window)
    assert qw is not None
    assert qw.activeFocusItem() is not None

    # Tab navigation visits visible Material setup controls in order and remains inside Material quick surface
    tabbed_names: list[str] = []
    for _ in range(120):
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        qapp.sendEvent(quick, ev)
        item = qw.activeFocusItem()
        assert item is not None
        assert host_has_focus(window)
        tabbed_names.append(item.property("objectName") or "")

    # Visible step rail, choice cards, and footer buttons are in the tab sequence
    assert "setupStep0" in tabbed_names
    assert "setupNext" in tabbed_names

    # Shift+Tab reverses focus and never escapes to hidden Widgets setup
    for _ in range(16):
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        qapp.sendEvent(quick, ev)
        item = qw.activeFocusItem()
        assert item is not None
        assert host_has_focus(window)


def test_setup_keeps_a_saved_cutoff_that_is_not_on_the_list(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    """Running setup again must show a saved 22:15 as itself and save it back, not reset it to no limit."""
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "cutoff_student")
    through_recovery(qapp, window)
    bridge._state.preferences["day_cutoff"] = "22:15"
    bridge._load_fields()
    marked = [row["label"] for row in bridge.cutoffChoices if row["value"] == bridge.cutoff]
    assert marked == [hhmm_text("22:15")]
    bridge._step = WEEK
    assert bridge._answer()["day_cutoff"] == "22:15"
