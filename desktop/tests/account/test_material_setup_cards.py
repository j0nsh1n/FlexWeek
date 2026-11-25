"""Material first-run setup as three steps of multiple-choice cards: what each card writes, when the detailed
controls show, what the preview draws, and Skip, Back, resume and Run setup again.

Expected values are worked out from the requirement (a card's own words), not from reading the bridge.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF
from PySide6.QtWidgets import QApplication

from desktop.native.setup_steps import HOMEWORK, REMINDERS, WEEK
from desktop.tests.account.support import (
    LightLaunches,
    account,
    create,
    material_launches,  # noqa: F401
    page,
    settle,
    shown,
    through_recovery,
)
from desktop.tests.material_support import qml, quick_of, visuals
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401


def _start(qapp: QApplication, launches: LightLaunches, name: str):
    window = launches.launch()
    bridge = account(window)
    create(qapp, window, name)
    through_recovery(qapp, window)
    return window, bridge


def _step_saved(window, step: int) -> bool:
    return (window.session.preferences or {}).get("setup", {}).get("step") == step


def _finish(qapp: QApplication, window, bridge) -> None:
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)


def _material_look() -> dict:
    return json.loads(look_file().read_text(encoding="utf-8")).get("material", {})


def _picked(cards: list) -> list[str]:
    return [card["value"] for card in cards if card["selected"]]


def test_setup_has_three_steps_and_opens_on_the_first_school_card(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "three_steps")
    assert [row["name"] for row in bridge.rail] == ["School hours", "Study hours", "Look & alerts"]
    assert bridge.setupStep == WEEK
    assert page(window) == "materialPage"
    assert [card["value"] for card in bridge.schoolCards] == ["8to3", "830to315", "9to330", "custom"]
    assert _picked(bridge.schoolCards) == ["8to3"]
    assert bridge.power is False


@pytest.mark.parametrize(
    ("card", "start", "minutes"),
    [("8to3", "08:00", 420), ("830to315", "08:30", 405), ("9to330", "09:00", 390)],
)
def test_each_school_card_writes_its_hours_monday_to_friday(
    qapp: QApplication, material_launches: LightLaunches, card: str, start: str, minutes: int
) -> None:
    window, bridge = _start(qapp, material_launches, "school_" + card)
    bridge.setSchoolPreset(card)
    assert _picked(bridge.schoolCards) == [card]
    bridge.setupNext()
    wait_until(qapp, lambda: _step_saved(window, HOMEWORK))
    settle(qapp, window)
    school = next(block for block in window.session.blocks if block["title"] == "School")
    assert (school["start"], school["duration_min"]) == (start, minutes)
    assert school["days"] == [0, 1, 2, 3, 4]


def test_each_study_card_writes_its_hours_and_the_planning_cards_their_style(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "study_cards")
    bridge.setupNext()
    wait_until(qapp, lambda: _step_saved(window, HOMEWORK))
    assert [card["value"] for card in bridge.studyCards] == ["after_school", "evenings", "anytime", "custom"]
    assert _picked(bridge.studyCards) == ["anytime"]
    bridge.setPlanning("manual")
    bridge.setStudyPreset("after_school")
    assert _picked(bridge.studyCards) == ["after_school"]
    bridge.setupNext()
    wait_until(qapp, lambda: _step_saved(window, REMINDERS))
    settle(qapp, window)
    prefs = window.session.preferences
    assert prefs["planning_style"] == "manual"
    assert prefs["work_windows"] == [{"days": [0, 1, 2, 3, 4], "start": "15:30", "end": "18:00"}]
    bridge.setupBack()
    assert bridge.setupStep == HOMEWORK
    bridge.setStudyPreset("evenings")
    assert bridge.workWindows[0]["start"] == "7:00 PM"
    bridge.setStudyPreset("anytime")
    assert bridge.workWindows == []


def test_the_look_and_reminder_cards_write_their_choices_and_open_the_week(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "last_step")
    bridge.setupNext()
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == REMINDERS)
    assert bridge.nextLabel == "Open my week"
    assert [card["value"] for card in bridge.reminderCards] == ["10", "5", "15", "off"]
    assert _picked(bridge.reminderCards) == ["5"]
    bridge.setReminderChoice("15")
    bridge.setLookPreset("Forest")
    bridge.setLookMode("dark")
    bridge.setLookDensity("compact")
    _finish(qapp, window, bridge)
    prefs = window.session.preferences
    assert prefs["reminder_lead_min"] == 15
    assert prefs["setup"].get("finished_at")
    assert (_material_look()["preset"], _material_look()["mode"], _material_look()["density"]) == (
        "Forest",
        "dark",
        "compact",
    )
    assert page(window) == "materialPage"


def test_no_reminders_is_written_as_reminders_off(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "no_reminders")
    bridge.setupNext()
    bridge.setupNext()
    bridge.setReminderChoice("off")
    assert _picked(bridge.reminderCards) == ["off"]
    _finish(qapp, window, bridge)
    assert window.session.preferences["reminders_enabled"] is False


def test_the_defaults_a_student_never_touches_stay_the_defaults(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    """The cutoff and the drag step are not on the simple cards, and stay no limit and 15 minutes."""
    window, bridge = _start(qapp, material_launches, "defaults")
    assert bridge.cutoff == "" and bridge.dragStep == 15
    bridge.setupNext()
    bridge.setupNext()
    _finish(qapp, window, bridge)
    prefs = window.session.preferences
    assert not prefs.get("day_cutoff")
    assert prefs.get("drag_step_min", 15) == 15


def test_the_detailed_controls_show_only_after_the_card_that_means_them(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "power_cards")
    for card in ("8to3", "830to315", "9to330"):
        bridge.setSchoolPreset(card)
        assert bridge.power is False
    assert not shown(window, "setupWeekDetails")
    bridge.setSchoolPreset("custom")
    assert bridge.power is True
    wait_until(qapp, lambda: shown(window, "setupWeekDetails"))
    bridge.setSchoolPreset("8to3")
    assert bridge.power is False
    wait_until(qapp, lambda: not shown(window, "setupWeekDetails"))
    for card in ("after_school", "evenings", "anytime"):
        bridge.setStudyPreset(card)
        assert bridge.power is False
    bridge.setStudyPreset("custom")
    assert bridge.power is True
    bridge.setStudyPreset("anytime")
    assert bridge.power is False
    bridge.setSoundOpen(True)
    assert bridge.power is True
    bridge.useDefaultSound()
    assert bridge.power is False
    for choice in ("10", "5", "15", "off"):
        bridge.setReminderChoice(choice)
    bridge.setLookPreset("Forest")
    bridge.setLookMode("light")
    bridge.setLookDensity("compact")
    assert bridge.power is False


def test_the_detailed_controls_write_the_same_fields_the_old_pages_did(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "power_writes")
    bridge.setSchoolPreset("custom")
    bridge.setClock24(True)
    bridge.setCutoff("21:00")
    bridge.setActivityTitle(0, "Soccer")
    bridge.toggleActivityDay(0, 1)
    bridge.toggleActivityDay(0, 3)
    bridge.setActivityStart(0, "4:00 pm")
    bridge.setActivityEnd(0, "17:30")
    bridge.setupNext()
    wait_until(qapp, lambda: _step_saved(window, HOMEWORK))
    settle(qapp, window)
    assert window.session.preferences["day_cutoff"] == "21:00"
    assert window.session.preferences["clock_24h"] is True
    soccer = next(block for block in window.session.blocks if block["title"] == "Soccer")
    assert (soccer["days"], soccer["start"], soccer["duration_min"]) == ([1, 3], "16:00", 90)
    assert soccer["category"] == "exercise"
    bridge.setStudyPreset("custom")
    bridge.setDragStep(5)
    bridge.addWorkPreset("Weekend mornings")
    bridge.setWorkSubject(0, "Math")
    bridge.setupNext()
    wait_until(qapp, lambda: _step_saved(window, REMINDERS))
    settle(qapp, window)
    prefs = window.session.preferences
    assert prefs["drag_step_min"] == 5
    assert prefs["work_windows"] == [{"days": [5, 6], "start": "10:00", "end": "12:00", "subject": "Math"}]
    bridge.setSoundOpen(True)
    bridge.setLead(20)
    tone = next(row["value"] for row in bridge.tones if row["value"] not in {"spotify", "chime"})
    bridge.setTone(tone)
    _finish(qapp, window, bridge)
    prefs = window.session.preferences
    assert prefs["reminder_lead_min"] == 20
    assert prefs["alarm_tone"] == tone


def test_a_spotify_alarm_without_a_link_stops_the_last_step(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "spotify_step")
    bridge.setupNext()
    bridge.setupNext()
    bridge.setSoundOpen(True)
    bridge.setTone("spotify")
    bridge.setupNext()
    assert bridge.phase == "setup" and bridge.setupStep == REMINDERS
    assert bridge.setupProblem.startswith("Paste a link that starts with https://open.spotify.com")


def test_the_preview_draws_exactly_what_was_entered(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "preview_exact")
    school = [
        (block["title"], block["column"], block["start"], block["end"], block["category"])
        for block in bridge.preview["blocks"]
    ]
    assert school == [("School", day, 480, 900, "class") for day in range(5)]
    assert bridge.previewNote == "Showing your school hours"
    # Study hours that are set show only from the study step on.
    bridge.setStudyPreset("after_school")
    assert all(block["category"] == "class" for block in bridge.preview["blocks"])
    # A sport with no days is not a block; with days it is, in its own colour.
    bridge.setSchoolPreset("custom")
    bridge.setActivityTitle(0, "Soccer")
    assert len(bridge.preview["blocks"]) == 5
    bridge.toggleActivityDay(0, 1)
    soccer = [block for block in bridge.preview["blocks"] if block["title"] == "Soccer"]
    assert [(b["column"], b["start"], b["end"]) for b in soccer] == [(1, 930, 1020)]
    assert bridge.previewNote == "Showing your school hours and sports and jobs"
    # No school days: nothing is drawn and the preview says so.
    for day in range(5):
        bridge.toggleSchoolDay(day)
    bridge.toggleActivityDay(0, 1)
    assert bridge.preview["blocks"] == []
    assert bridge.previewNote.startswith("Nothing to show yet")
    bridge.toggleSchoolDay(0)
    bridge.toggleSchoolDay(2)
    wait_until(qapp, lambda: bridge.setupStep == WEEK)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == HOMEWORK)
    study = [b for b in bridge.preview["blocks"] if b["category"] == "study"]
    assert [(b["title"], b["start"], b["end"]) for b in study] == [("Study hours", 930, 1080)] * 5
    assert not any(block["title"] == "Soccer" for block in bridge.preview["blocks"])


def test_overlapping_blocks_on_a_day_sit_side_by_side(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "preview_lanes")
    bridge.setSchoolPreset("custom")
    bridge.setActivityTitle(0, "Robotics")
    bridge.toggleActivityDay(0, 0)
    bridge.setActivityStart(0, "2:00 pm")
    bridge.setActivityEnd(0, "4:00 pm")
    monday = [b for b in bridge.preview["blocks"] if b["column"] == 0]
    lanes = sorted((b["title"], b["lane"], b["lanes"]) for b in monday)
    assert lanes == [("Robotics", 1, 2), ("School", 0, 2)]
    tuesday = [b for b in bridge.preview["blocks"] if b["column"] == 1]
    assert [(b["lane"], b["lanes"]) for b in tuesday] == [(0, 1)]


def test_back_and_skip_this_step_keep_nothing_from_the_step(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "back_skip")
    assert bridge.backVisible is False
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == HOMEWORK)
    assert bridge.backVisible is True and bridge.skipStepVisible is True
    bridge.setPlanning("manual")
    bridge.setupSkip()
    assert bridge.setupStep == REMINDERS
    assert bridge.skipStepVisible is False and bridge.skipVisible is True
    settle(qapp, window)
    assert window.session.preferences.get("planning_style") != "manual"
    bridge.setupBack()
    assert bridge.setupStep == HOMEWORK


def test_skip_setup_on_the_last_step_puts_the_look_it_opened_with_back(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "skip_look")
    bridge.setupNext()
    bridge.setupNext()
    opened = bridge.lookPreset
    bridge.setLookPreset("Forest")
    assert bridge.lookPreset == "Forest" and _material_look()["preset"] == "Forest"
    bridge.setupSkipAll()
    wait_until(qapp, lambda: bridge.phase == "app")
    assert _material_look()["preset"] == opened


def test_setup_resumes_on_the_last_step_from_a_step_the_older_setup_ended_on(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "resume_old")
    state = window._setup_state(first_run=False)
    cases = ((0, WEEK), (2, WEEK), (WEEK, WEEK), (HOMEWORK, HOMEWORK), (6, REMINDERS), (7, REMINDERS))
    for old, expected in cases:
        bridge.open_setup(state, old)
        assert bridge.setupStep == expected


def test_run_setup_again_opens_the_same_cards_on_what_was_kept(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "run_again")
    bridge.setSchoolPreset("830to315")
    bridge.setupNext()
    bridge.setStudyPreset("evenings")
    bridge.setupNext()
    bridge.setReminderChoice("15")
    _finish(qapp, window, bridge)
    window._run_setup_again()
    wait_until(qapp, lambda: bridge.phase == "setup")
    assert bridge.setupStep == WEEK
    assert page(window) == "materialPage" and shown(window, "setupFlow")
    assert _picked(bridge.schoolCards) == ["830to315"]
    assert bridge.power is False
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == HOMEWORK)
    assert _picked(bridge.studyCards) == ["evenings"]
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == REMINDERS)
    assert _picked(bridge.reminderCards) == ["15"]


def test_run_setup_again_on_a_week_with_sports_opens_the_detailed_controls(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window, bridge = _start(qapp, material_launches, "run_again_power")
    bridge.setSchoolPreset("custom")
    bridge.setActivityTitle(0, "Band")
    bridge.toggleActivityDay(0, 2)
    bridge.setupNext()
    bridge.setupNext()
    _finish(qapp, window, bridge)
    window._run_setup_again()
    wait_until(qapp, lambda: bridge.phase == "setup")
    assert _picked(bridge.schoolCards) == ["custom"]
    assert bridge.power is True


def _scene_rect(item: QObject) -> tuple:
    top_left = item.mapToScene(QPointF(0.0, 0.0))
    bottom_right = item.mapToScene(
        QPointF(float(item.property("width")), float(item.property("height")))
    )
    return (top_left.x(), top_left.y(), bottom_right.x(), bottom_right.y())


def _setup_flow(window) -> QObject:
    return qml(quick_of(window).root, "setupFlow")


def test_every_study_hours_card_ends_above_the_footer(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    """At 1280x800 the Study hours step shows all its cards above the pinned footer, as the
    School hours step does, instead of cutting the last row off at it."""
    window, bridge = _start(qapp, material_launches, "study_fits")
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == HOMEWORK)
    settle(qapp, window)
    flow = _setup_flow(window)
    footer_top = _scene_rect(qml(flow, "setupFooterBar"))[1]
    cards = [
        item
        for item in visuals(flow)
        if str(item.objectName()).startswith(("setupPlanning-", "setupStudy-"))
    ]
    assert len(cards) == 7
    for card in cards:
        assert _scene_rect(card)[3] <= footer_top, card.objectName()
