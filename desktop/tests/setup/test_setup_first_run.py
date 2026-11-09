"""First-run setup: each page kept as the student leaves it, every page skippable, and setup never
back once it is finished or skipped, unless the student runs it again from Settings."""

# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
from __future__ import annotations

import json
from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.setup import DONE, FIRST, HOMEWORK, REMINDERS, STYLE, WEEK
from desktop.tests.setup.support_new_account import (
    Launcher,
    launcher,  # noqa: F401
    locked,
    new_account,
    page,
    sign_in,
    sign_up,
    written,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401

# A Monday morning, so the first homework's due day and the plan for it both lie in the week the new
# account opens on.
MONDAY_MORNING = datetime(2026, 11, 2, 9, 0)


def test_a_new_account_goes_from_its_recovery_codes_to_setup(qapp: QApplication, launcher: Launcher) -> None:
    window = new_account(qapp, launcher, "setup_first")
    setup = window.setup_page
    assert setup.step == STYLE
    assert not setup.back.isVisible()
    assert setup.skip.isVisible() and setup.next.text() == "Next"
    assert setup.rail_items[0].property("current") is True
    assert not setup.rail_items[1].isEnabled(), "a step not reached yet cannot be jumped to"


def test_every_page_is_kept_when_the_student_leaves_it(
    qapp: QApplication,
    launcher: Launcher,
    clock: FakeClock,
) -> None:
    clock.set(MONDAY_MORNING)
    window = new_account(qapp, launcher, "setup_walk")
    setup = window.setup_page
    setup.style_cards["dashboard"].chosen.emit()
    setup.next.click()
    written(qapp, window)
    stored = json.loads(look_file().read_text())
    assert stored["layout"]["main"] == "bento", "the look belongs to this computer"
    assert stored["layout"]["options"]["bento"]["look"] == "preset:bento-indigo"
    assert window.session.preferences["theme_pack"] == "light-frost"
    assert window.session.preferences["setup"]["step"] == WEEK

    assert setup.step == WEEK
    setup.school_times.set_span("08:00", 390)
    setup.activities[0].name.setText("Soccer")
    setup.activities[0].days.set_days([1, 3])
    setup._add_activity(title="Band", days=[0], start="16:00", minutes=60)
    setup.cutoff.setCurrentIndex(setup.cutoff.findData("22:00"))
    setup.next.click()
    written(qapp, window)
    assert locked(window) == {
        "school": ("School", "08:00", (0, 1, 2, 3, 4), 390),
        "activity-1": ("Soccer", "15:30", (1, 3), 90),
        "activity-2": ("Band", "16:00", (0,), 60),
    }
    assert window.session.revision == 1
    assert window.session.preferences["day_cutoff"] == "22:00"

    setup.planning_buttons["auto"].setChecked(True)
    assert setup.drag_buttons[5].isChecked(), "five minutes unless the student picks fifteen"
    setup.drag_buttons[15].setChecked(True)
    setup.work_editor.set_windows([{"days": [0, 1, 2, 3, 4], "start": "19:00", "end": "21:00"}])
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences["planning_style"] == "auto"
    assert window.session.preferences["drag_step_min"] == 15
    assert window.hand.step == 15
    assert window.session.preferences["work_windows"] == [
        {"days": [0, 1, 2, 3, 4], "start": "19:00", "end": "21:00"}
    ]
    assert not window.session.preferences.get("study_windows"), "setup no longer asks for study times"

    assert setup.reminders.isChecked(), "setup turns reminders on unless the student says no"
    setup.lead.setValue(15)
    setup.tone_buttons["glass"].setChecked(True)
    setup.next.click()
    written(qapp, window)
    prefs = window.session.preferences
    assert (prefs["reminders_enabled"], prefs["reminder_lead_min"], prefs["alarm_tone"]) == (
        True,
        15,
        "glass",
    )

    setup.homework_rows[0].name.setText("History essay")
    setup.homework_rows[0].minutes.setValue(90)
    setup.next.click()
    written(qapp, window)
    essay = next(item for item in window.session.assignments.values() if item["title"] == "History essay")
    assert essay["estimate_min"] == 90
    assert essay["due"] == "2026-11-03", "the next school day after Monday 2 November, no time"
    sessions = [block for block in window.session.blocks if block.get("assignment_id") == essay["id"]]
    assert sessions and all(block.get("start") for block in sessions), "Plan it for me gave it a time"

    assert setup.step == DONE
    summary = setup.summary_text()
    assert summary[0] == "Bento in Indigo"
    # Untouched, the clock is the new account's 12-hour one.
    assert "Soccer Tue, Thu 3:30 PM–5:00 PM" in summary[1] and "Band Mon 4:00 PM–5:00 PM" in summary[1]
    assert summary[4] == "History essay"
    setup.next.click()
    written(qapp, window)
    assert page(window) == "weekPage"
    assert window._layout["main"] == "bento"
    assert window.session.preferences["setup"]["finished_at"]
    launcher.quit(window)
    again = sign_in(qapp, launcher, "setup_walk")
    assert page(again) == "weekPage", "setup does not come back once it is finished"
    assert again.session.preferences["alarm_tone"] == "glass"


def test_skipping_every_page_keeps_nothing_and_setup_never_returns(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_skipper")
    setup = window.setup_page
    visited = []
    while setup.step != DONE:
        visited.append(setup.step)
        if setup.step == HOMEWORK:
            assert any(
                "Homework can be planned at any time of day." in label.text()
                for label in setup.pages[HOMEWORK].findChildren(QLabel)
            )
            setup.work_editor.set_windows([{"days": [0, 1, 2, 3, 4], "start": "15:30", "end": "18:00"}])
        setup.skip.click()
    assert visited == [STYLE, WEEK, HOMEWORK, REMINDERS, FIRST]
    setup.next.click()
    written(qapp, window)
    assert page(window) == "weekPage"
    assert window.session.blocks == [] and window.session.assignments == {}
    prefs = window.session.preferences
    assert prefs["reminders_enabled"] is True, "a skipped page changes nothing, and reminders start on"
    assert prefs.get("planning_style", "suggest") == "suggest"
    assert not prefs.get("work_windows"), "skipping does not keep hours entered on that page"
    assert prefs["setup"]["finished_at"]
    assert not look_file().exists() or json.loads(look_file().read_text())["layout"]["main"] == "classic"
    launcher.quit(window)

    again = sign_in(qapp, launcher, "setup_skipper")
    assert page(again) == "weekPage", "an empty week does not bring setup back"


def test_skip_setup_is_remembered(qapp: QApplication, launcher: Launcher) -> None:
    window = new_account(qapp, launcher, "setup_skip_all")
    window.setup_page.skip_all.click()
    written(qapp, window)
    assert page(window) == "weekPage"
    assert window.session.preferences["setup"]["finished_at"]
    launcher.quit(window)
    again = sign_in(qapp, launcher, "setup_skip_all")
    assert page(again) == "weekPage"


def test_a_skip_before_the_accounts_preferences_arrive_is_still_written(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    """A new account opens setup before its preferences have loaded. A skip in that moment waits for
    them, and is written when they come, rather than forgotten."""
    window = new_account(qapp, launcher, "setup_quick")
    window.session.preferences = None
    window.setup_page.skip_all.click()
    assert page(window) == "weekPage"
    assert window._setup_prefs, "nothing to write it into yet"
    window.session._fetch_preferences()
    written(qapp, window)
    assert window.session.preferences["setup"]["finished_at"]
    launcher.quit(window)
    again = sign_in(qapp, launcher, "setup_quick")
    assert page(again) == "weekPage"


def test_a_quit_resumes_on_the_step_it_left_with_earlier_answers_kept(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_quitter")
    setup = window.setup_page
    setup.style_cards["retro"].chosen.emit()
    setup.next.click()
    setup.school_times.set_span("07:45", 435)
    setup.next.click()
    assert setup.step == HOMEWORK
    written(qapp, window)
    launcher.quit(window)

    again = sign_in(qapp, launcher, "setup_quitter")
    wait_until(qapp, lambda: page(again) == "setupPage", what="setup resumed")
    resumed = again.setup_page
    assert resumed.step == HOMEWORK
    assert again._layout["main"] == "retro", "the look chosen before the quit is the one on screen"
    resumed.back.click()
    assert resumed.step == WEEK
    assert resumed.school_times.span() == ("07:45", 435)


def test_a_new_account_starts_at_the_beginning_not_where_the_last_one_left(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    first = new_account(qapp, launcher, "setup_before")
    first.setup_page.skip.click()
    first.setup_page.skip.click()
    written(qapp, first)
    first.session.logout()
    wait_until(qapp, lambda: page(first) == "authPage", what="the sign-in page after signing out")
    sign_up(qapp, first, "setup_after")
    assert first.setup_page.step == STYLE
    assert first.setup_page.homework_rows[0].name.text() == ""


def test_an_account_already_in_use_with_work_in_it_is_not_asked_to_run_setup(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    """Setup kept its place only from one version on. An account already in use has nothing to record,
    and must not be walked through setup the first time it opens that version."""
    window = new_account(qapp, launcher, "setup_veteran")
    window.session.add_homework(
        {"id": "essay", "title": "Essay", "due": sunday_due(window.session.week_start), "estimate_min": 60}
    )
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty, what="the save")
    assert "setup" not in window.session.preferences
    launcher.quit(window)
    again = sign_in(qapp, launcher, "setup_veteran")
    assert page(again) == "weekPage"


def test_run_setup_again_opens_filled_in_with_the_current_choices(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_rerun")
    setup = window.setup_page
    setup.style_cards["night"].chosen.emit()
    setup.next.click()
    setup.activities[0].name.setText("Soccer")
    setup.activities[0].days.set_days([1, 3])
    setup.next.click()
    setup.skip.click()
    setup.reminders.setChecked(False)
    setup.next.click()
    setup.skip_all.click()
    written(qapp, window)
    assert page(window) == "weekPage"

    window._open_settings()
    assert page(window) == "settingsPage"
    window._settings.findChild(QPushButton, "prefsRunSetup").click()
    wait_until(qapp, lambda: page(window) == "setupPage", what="setup opened again")
    assert setup.step == STYLE
    assert setup.style_cards["night"].is_selected(), "the style in use shows as picked"
    assert [row.name.text() for row in setup.activities] == ["Soccer"]
    assert setup.activities[0].days.days() == [1, 3]
    assert not setup.reminders.isChecked(), "reminders are as the student left them, not on again"
    written(qapp, window)
    setup.skip_all.click()
    written(qapp, window)
    assert page(window) == "weekPage"
    assert window._layout["main"] == "timeline"
