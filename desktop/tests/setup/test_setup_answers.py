"""What setup's pages keep and where it shows afterwards: the look, the hours homework can be planned
in (and the same hours edited in Settings), the test reminder, and the first homework."""

# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from desktop.native.setup import DONE, FIRST, HOMEWORK, REMINDERS
from desktop.native.widgets import AvailabilityDialog
from desktop.tests.setup.support_new_account import (
    Launcher,
    launcher,  # noqa: F401
    new_account,
    sign_in,
    written,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file, qapp  # noqa: F401

SPOTIFY = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
# The clock starts on Thursday 5 November 2026, so the next school day is Friday the 6th.
NEXT_SCHOOL_DAY = "2026-11-06"


def test_a_style_look_is_saved_and_selected_in_settings(qapp: QApplication, launcher: Launcher) -> None:
    window = new_account(qapp, launcher, "setup_style_look")
    setup = window.setup_page
    setup.carousel.look_swatches["preset:high-contrast"].click()
    setup.next.click()
    written(qapp, window)
    saved = json.loads(look_file().read_text())
    assert saved["layout"]["main"] == "classic"
    assert saved["layout"]["options"]["classic"]["look"] == "preset:high-contrast"

    while setup.step != DONE:
        setup.skip.click()
    assert setup.summary_text()[0] == "Today's app in High contrast"
    setup.skip_all.click()
    written(qapp, window)
    window._open_settings()
    choice = window._settings.findChild(QComboBox, "layoutMain-look")
    assert choice is not None
    assert choice.currentData() == "preset:high-contrast"


def test_setup_saves_the_account_pack_when_a_pack_look_is_picked(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_pack_choice")
    setup = window.setup_page
    setup.findChild(QPushButton, "setupOwnLook").click()
    setup.look_cards["classic"].chosen.emit()
    setup.next.click()
    dark = next(button for button in setup.colours.buttons() if button.property("value") == "pack:dark-frost")
    dark.click()
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences["theme_pack"] == "dark-frost"
    assert setup._layout["options"]["classic"]["look"] == "pack:dark-frost"


def test_a_work_window_chosen_in_setup_reaches_the_account(qapp: QApplication, launcher: Launcher) -> None:
    window = new_account(qapp, launcher, "setup_work_hours")
    setup = window.setup_page
    setup.skip.click()
    setup.skip.click()
    assert setup.step == HOMEWORK
    chosen = {"days": [0, 1, 2, 3, 4], "start": "15:30", "end": "18:00", "subject": "Math"}
    setup.work_editor.set_windows([chosen])
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences["work_windows"] == [chosen]
    launcher.quit(window)

    again = sign_in(qapp, launcher, "setup_work_hours")
    assert again.session.preferences["work_windows"] == [chosen]


def test_settings_saves_work_windows_with_existing_availability(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "settings_work_hours")
    window.setup_page.skip_all.click()
    written(qapp, window)
    protected = [{"days": [0], "start": "19:00", "duration_min": 60, "kind": "meal"}]
    weekdays = {"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "21:00"}
    assert window.session.save_availability(protected, "22:00", [weekdays])
    wait_until(
        qapp,
        lambda: not window.session.busy and window.session.preferences["work_windows"] == [weekdays],
        what="the first availability saved",
    )

    weekend = {"days": [5, 6], "start": "10:00", "end": "16:00"}
    sent: list[tuple[list[dict], str | None, list[dict]]] = []
    save = window.session.save_availability

    def record(kept_protected: list[dict], cutoff: str | None, hours: list[dict]) -> bool:
        sent.append((kept_protected, cutoff, hours))
        return save(kept_protected, cutoff, hours)

    window.session.save_availability = record

    def choose() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, AvailabilityDialog)
        for day in (5, 6):
            dialog._open_picker(kind="study", day=day)
            dialog.picker_start.setTime(QTime(10, 0))
            dialog.picker_end.setTime(QTime(16, 0))
            dialog.picker_add.click()
        dialog.accept()

    QTimer.singleShot(0, choose)
    window._open_availability()
    wait_until(
        qapp,
        lambda: not window.session.busy and window.session.preferences["work_windows"] == [weekdays, weekend],
        what="the weekend hours saved beside the weekday ones",
    )
    prefs = window.session.preferences
    assert sent == [(protected, "22:00", [weekdays, weekend])]
    assert prefs["protected"] == protected
    assert "study_windows" not in prefs
    assert prefs["day_cutoff"] == "22:00"


def test_a_test_reminder_rings_the_chosen_sound_and_gives_the_spotify_app_the_link(
    qapp: QApplication,
    launcher: Launcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = new_account(qapp, launcher, "setup_tester")
    setup = window.setup_page
    for _ in range(3):
        setup.skip.click()
    assert setup.step == REMINDERS
    rung: list[str] = []
    opened: list[str] = []
    monkeypatch.setattr(window._bell, "once", lambda tone, _volume: rung.append(tone) or True)
    monkeypatch.setattr("desktop.native.spotify.open_address", lambda address: opened.append(address) or True)
    setup.tone_buttons["bright"].setChecked(True)
    setup.test.click()
    assert rung == ["bright"]
    assert setup.test_result.text().startswith("Sent.")
    setup.tone_buttons["spotify"].setChecked(True)
    setup.test.click()
    assert opened == [], "no link yet, so nothing to open"
    assert "Spotify link" in setup.test_result.text()
    setup.spotify.setText(SPOTIFY)
    setup.test.click()
    assert opened == ["spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"], "the playlist, in the Spotify app"
    assert rung[-1] == "chime", "a reminder never starts music; it chimes"


def test_back_then_next_does_not_add_the_first_homework_twice(qapp: QApplication, launcher: Launcher) -> None:
    window = new_account(qapp, launcher, "setup_twice")
    setup = window.setup_page
    for _ in range(4):
        setup.skip.click()
    assert setup.step == FIRST
    setup.homework_rows[0].name.setText("Chem lab report")
    setup.next.click()
    written(qapp, window)
    setup.back.click()
    setup.homework_rows[0].name.setText("Chem lab report")
    setup.homework_rows[0].minutes.setValue(120)
    setup.next.click()
    written(qapp, window)
    titles = [item["title"] for item in window.session.assignments.values()]
    assert titles == ["Chem lab report"]
    assert next(iter(window.session.assignments.values()))["estimate_min"] == 120


def test_a_first_homework_due_at_a_set_time_keeps_it_and_one_without_has_none(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_due_time")
    setup = window.setup_page
    for _ in range(4):
        setup.skip.click()
    assert setup.step == FIRST
    oral = setup.homework_rows[0]
    oral.name.setText("French oral")
    oral.due.timed.setChecked(True)
    oral.due.time.setTime(QTime(9, 0))
    setup.add_homework.click()
    setup.homework_rows[1].name.setText("Reading log")
    setup.next.click()
    written(qapp, window)
    dues = {item["title"]: item["due"] for item in window.session.assignments.values()}
    assert dues == {"French oral": f"{NEXT_SCHOOL_DAY}T09:00", "Reading log": NEXT_SCHOOL_DAY}
