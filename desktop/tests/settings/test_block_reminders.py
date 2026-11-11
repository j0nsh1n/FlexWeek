"""Reminders, followed to what the student sees, with the clock held.

The reminder engine used to be checked by listening to the session's `alerts` signal, which proves a
notice was made, not that anyone saw it. These tests watch the tray message (through a stand-in tray,
since offscreen Qt has none), the toast under the top bar and the status line.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import Account, account, open_light, open_light_window  # noqa: F401
from desktop.tests.settings.support_reminders import (
    PRACTICE_NOTICE,
    REMINDER,
    add_practice,
    at,
    choose,
    seen,
    tick,
    with_stand_ins,
)
from desktop.tests.window_support import free, qapp, settled  # noqa: F401

# The preferences table as 0.14 left it, for an account made before reminders were on by default.
PREFERENCES_0_14 = """
    CREATE TABLE preferences (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        theme TEXT NOT NULL DEFAULT 'system' CHECK(theme IN ('system', 'slate', 'nocturne')),
        reminders_enabled INTEGER NOT NULL DEFAULT 0 CHECK(reminders_enabled IN (0, 1)),
        reminder_lead_min INTEGER NOT NULL DEFAULT 5
            CHECK(reminder_lead_min >= 0 AND reminder_lead_min <= 120),
        reminder_sound INTEGER NOT NULL DEFAULT 1 CHECK(reminder_sound IN (0, 1)),
        reminder_dnd_override INTEGER NOT NULL DEFAULT 0 CHECK(reminder_dnd_override IN (0, 1)),
        timer_work_min INTEGER NOT NULL DEFAULT 30,
        timer_break_min INTEGER NOT NULL DEFAULT 15,
        timer_long_break_min INTEGER NOT NULL DEFAULT 30,
        timer_long_break_every INTEGER NOT NULL DEFAULT 4,
        auto_split_pomodoro INTEGER NOT NULL DEFAULT 0 CHECK(auto_split_pomodoro IN (0, 1)),
        default_spotify_url TEXT,
        alarms_json TEXT NOT NULL DEFAULT '[]',
        availability_json TEXT NOT NULL DEFAULT '{}',
        comfort_json TEXT NOT NULL DEFAULT '{}'
    )
"""
COLUMNS_0_14 = (
    "user_id, theme, reminders_enabled, reminder_lead_min, reminder_sound, reminder_dnd_override,"
    " timer_work_min, timer_break_min, timer_long_break_min, timer_long_break_every,"
    " auto_split_pomodoro, default_spotify_url, alarms_json, availability_json, comfort_json"
)


def make_it_0_14(database: Path, reminders: bool) -> None:
    """The account as 0.14 left it: its preferences in 0.14's table, with reminders as given."""
    with contextlib.closing(sqlite3.connect(database)) as db, db:
        db.execute("ALTER TABLE preferences RENAME TO preferences_now")
        db.execute(PREFERENCES_0_14)
        db.execute(f"INSERT INTO preferences({COLUMNS_0_14}) SELECT {COLUMNS_0_14} FROM preferences_now")
        db.execute("DROP TABLE preferences_now")
        db.execute("UPDATE preferences SET reminders_enabled = ?", (int(reminders),))


class OldComputer:
    """One account, as 0.14 left it, opened again and again on the same database: the window of one
    run is closed before the next opens on what that run saved. All are closed when the test ends."""

    def __init__(self, qapp: QApplication, folder: Path, made: Account) -> None:
        self._qapp, self._folder, self._made = qapp, folder, made
        self._runs = 0
        self._running: tuple[NativeWindow, object] | None = None
        folder.mkdir(parents=True, exist_ok=True)
        self.database = folder / "start.db"
        with contextlib.closing(sqlite3.connect(made.database)) as kept, contextlib.closing(
            sqlite3.connect(self.database)
        ) as new:
            kept.backup(new)
        make_it_0_14(self.database, reminders=False)

    def open(self) -> NativeWindow:
        self.close()
        self._runs += 1
        made = Account(self.database, self._made.look, self._made.user_id)
        window, api = open_light_window(self._qapp, self._folder / f"run-{self._runs}", made, (1280, 860))
        self._running = (window, api)
        self.database = self._folder / f"run-{self._runs}" / "flexweek.db"
        return with_stand_ins(window)

    def close(self) -> None:
        if self._running is None:
            return
        window, api = self._running
        self._running = None
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        free(window)
        api.close()


@pytest.fixture()
def old_computer(
    qapp: QApplication, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[OldComputer]:
    made = account(qapp, tmp_path_factory.getbasetemp() / "light-account")
    computer = OldComputer(qapp, tmp_path / "old-computer", made)
    yield computer
    computer.close()


@pytest.fixture()
def new_window(open_light: Callable[..., NativeWindow]) -> NativeWindow:
    """A new account past setup, with a tray and a bell that note what they are asked."""
    return with_stand_ins(open_light(size=(1280, 860)))


def test_a_block_saved_inside_its_lead_reminds_at_once_and_only_once(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    """At 18:38 a block for 18:45 with a 10-minute lead. Its lead began at 18:35, so the reminder was due
    before the block existed, and a check that only looks back two minutes never found it. It comes at
    the first check after the save, and never again."""
    window = new_window
    at(18, 38)
    choose(qapp, window, reminders_enabled=True, reminder_lead_min=10)
    add_practice(qapp, window)
    tick(qapp, window, 38)
    assert seen(window) == {"tray": [PRACTICE_NOTICE], "toast": REMINDER}
    assert window._bell.once_rung == ["chime"]
    for minute in range(39, 49):
        tick(qapp, window, minute)
    assert window._tray_icon.shown == [PRACTICE_NOTICE]
    assert window._bell.once_rung == ["chime"]


def test_a_block_saved_before_its_lead_reminds_when_the_lead_begins(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    """Without a tray to carry it, the window alone says it."""
    window = new_window
    window._tray_icon = None
    at(18, 20)
    choose(qapp, window, reminders_enabled=True, reminder_lead_min=10)
    add_practice(qapp, window)
    for minute in range(20, 35):
        tick(qapp, window, minute)
        assert window._bell.once_rung == [], f"reminded at 18:{minute}"
    tick(qapp, window, 35)
    assert window.toast.isVisible() and window.toast.text() == REMINDER
    for minute in range(36, 50):
        tick(qapp, window, minute)
    # With no tray the reminder is kept on screen, and the start replaces it with "starts now", which
    # chimes once more; nothing else rings.
    assert window._bell.once_rung == ["chime", "chime"]
    assert window.toast.text() == "Guitar practice starts now — 6:45 PM · Thu"


def test_a_new_account_reminds_without_being_asked(qapp: QApplication, new_window: NativeWindow) -> None:
    """Setup skipped, nothing chosen: blocks still remind, at the lead the account starts with."""
    window = new_window
    assert window.session.preferences["reminders_enabled"] is True
    lead = int(window.session.preferences["reminder_lead_min"])
    at(18, 20)
    add_practice(qapp, window)
    tick(qapp, window, 45 - lead)
    assert window._tray_icon.shown == [PRACTICE_NOTICE]


def test_an_account_from_0_14_with_reminders_off_reminds_after_the_update(
    qapp: QApplication, old_computer: OldComputer
) -> None:
    """Its reminders were off only because setup never asked, so the update turns them on."""
    window = old_computer.open()
    assert window.session.preferences["reminders_enabled"] is True
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10)
    add_practice(qapp, window)
    tick(qapp, window, 35)
    assert window._tray_icon.shown == [PRACTICE_NOTICE]


def test_reminders_turned_off_after_the_update_stay_off(
    qapp: QApplication, old_computer: OldComputer
) -> None:
    """The update happens once. After it, the student's own choice stands, restart after restart."""
    first = old_computer.open()
    assert first.session.preferences["reminders_enabled"] is True
    choose(qapp, first, reminders_enabled=False, reminder_lead_min=10)
    window = old_computer.open()
    assert window.session.preferences["reminders_enabled"] is False
    at(18, 30)
    add_practice(qapp, window)
    for minute in range(30, 50):
        tick(qapp, window, minute)
    assert window._tray_icon.shown == []
    assert window._bell.once_rung == []


def test_the_toast_keeps_a_reminder_until_something_more_important(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    """"Saved preferences." wrote over the reminder. A save's confirmation is less than a reminder, so
    it is not said at all; something the student has to read now is more."""
    window = new_window
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10)
    add_practice(qapp, window)
    tick(qapp, window, 35)
    assert window.toast.text() == REMINDER
    window.session.save_preferences({"alert_volume": 70})
    settled(qapp, window)
    assert window.session.message == "Saved preferences."
    assert window.toast.text() == REMINDER
    window.session.add_block(
        {"id": "dinner", "title": "Dinner", "kind": "locked", "category": "meals", "start": "19:30",
         "duration_min": 30, "days": [3]}
    )
    window.session.save()
    settled(qapp, window)
    assert window.toast.text() == REMINDER
    window.session.select_block(None, None)
    window.session.copy_selected()
    assert window.toast.text() == "Select a block before copying it."


def test_got_it_on_a_reminder_left_on_screen_takes_its_toast_away_too(
    qapp: QApplication, new_window: NativeWindow
) -> None:
    window = new_window
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10, reminder_dnd_override=True)
    add_practice(qapp, window)
    tick(qapp, window, 35)
    assert window.alert_strip.isVisible() and window.toast.text() == REMINDER
    window.alert_strip.dismiss.click()
    assert not window.alert_strip.isVisible()
    assert not window.toast.isVisible()
