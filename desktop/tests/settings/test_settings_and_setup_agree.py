"""The words and numbers that have one place that decides them: the Spotify link note, the reminder lead,
the Availability sheet's homework cutoff and the snooze length."""

from __future__ import annotations

import ast
import inspect

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from desktop.native import remind
from desktop.native.settings import AlarmRingDialog
from desktop.native.settings_copy import SPOTIFY_TONE_NOTE
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811

HINT = (
    "Plays when a block starts if the alarm sound is Spotify, or when focus starts if the focus sound"
    " is Spotify."
)
NO_HOMEWORK_AFTER = ["No limit", "20:00", "20:30", "21:00", "21:30", "22:00", "22:30", "23:00"]


def texts(box: QComboBox) -> list[tuple[str, object]]:
    return [(box.itemText(row), box.itemData(row)) for row in range(box.count())]


# The Spotify link


def test_the_link_note_does_not_say_a_block_without_a_link_plays_nothing(qapp: QApplication) -> None:
    assert SPOTIFY_TONE_NOTE.startswith(HINT)
    assert "without a link" not in SPOTIFY_TONE_NOTE
    assert "Reminders before a block and the end of a focus session play Chime." in SPOTIFY_TONE_NOTE


# The reminder lead


def test_the_default_lead_is_the_engines_and_is_five() -> None:
    assert flexweek_engine.REMINDER_LEAD_DEFAULT_MIN == 5
    assert remind.reminder_lead_min({}) == 5
    assert remind.reminder_lead_min({"reminder_lead_min": None}) == 5
    assert remind.reminder_lead_min({"reminder_lead_min": 12}) == 12


# The constants


def test_python_keeps_no_copy_of_the_engines_constants() -> None:
    tree = ast.parse(inspect.getsource(remind))
    assigned = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for name in ("REMINDER_WINDOW_MIN", "ALARM_SNOOZE_MIN", "ALARM_SNOOZE_MS"):
        value = assigned[name]
        assert isinstance(value, ast.Attribute), f"{name} is written down again, not read"
        assert isinstance(value.value, ast.Name) and value.value.id == "flexweek_engine", name
        assert getattr(remind, name) == getattr(flexweek_engine, name)


def test_the_snooze_button_and_the_snooze_length_agree(qapp: QApplication) -> None:
    dialog = AlarmRingDialog(None, {"name": "Wake up", "time": "06:45"}, "")
    button = dialog.findChild(QPushButton, "alarmSnooze")
    assert isinstance(button, QPushButton)
    snoozed_for = remind.snooze_until(1_000_000) - 1_000_000
    assert snoozed_for % 60_000 == 0
    assert button.text() == f"Snooze {snoozed_for // 60_000} minutes"
    dialog.close()
