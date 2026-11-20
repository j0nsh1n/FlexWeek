"""Material's Help lists exactly the keys its window answers to: every listed chord is handled in the
source that handles it, and every one-letter shortcut Main.qml registers is listed."""

from __future__ import annotations

import re
from pathlib import Path

from desktop.native.settings_copy import HELP_LETTER_KEYS, help_keys, keys_words

NATIVE = Path(__file__).resolve().parents[2] / "native"
MAIN = (NATIVE / "material/qml/Main.qml").read_text()
BLOCK = (NATIVE / "material/qml/week/WeekBlock.qml").read_text()
HOURS = (NATIVE / "material/qml/hours/HoursPane.qml").read_text()
WINDOW = (NATIVE / "window.py").read_text()

# Where each listed chord is handled, as text that appears there only if the handling does.
HANDLED = {
    "Ctrl+Shift+F": (MAIN, '"Ctrl+Shift+F"'),
    "F1": (MAIN, '"F1"'),
    "Ctrl+N": (MAIN, '"Ctrl+N"'),
    "Ctrl+Shift+L": (MAIN, '"Ctrl+Shift+L"'),
    "Ctrl+Z": (MAIN, '"Ctrl+Z"'),
    "Ctrl+Y or Ctrl+Shift+Z": (MAIN, '["Ctrl+Shift+Z", "Ctrl+Y"]'),
    "Ctrl+C then Ctrl+V": (BLOCK, "ctrl && event.key === Qt.Key_C"),
    "Ctrl+D": (BLOCK, "Qt.Key_D"),
    "Delete": (BLOCK, "Qt.Key_Delete"),
    "Ctrl+S": (WINDOW, "Key.Key_S"),
    "Ctrl+= - 0": (MAIN, '"Ctrl+0"'),
    "Ctrl and the mouse wheel": (HOURS, "acceptedModifiers: Qt.ControlModifier"),
}


def test_every_listed_key_is_handled_and_no_other_chord_is_listed() -> None:
    spoken = {keys_words(key) for key, _ in help_keys(False, False, material=True)}
    assert spoken == set(HANDLED)
    for chord, (source, needle) in HANDLED.items():
        assert needle in source, chord
    assert re.search(r'"Ctrl\+V"', MAIN), "Ctrl+V pastes what Ctrl+C copied"


def test_the_letter_keys_listed_are_the_ones_main_registers() -> None:
    registered = set(re.findall(r'LetterShortcut \{ sequence: "(\w)"', MAIN))
    listed = {
        letter for key, _ in HELP_LETTER_KEYS for letter in re.findall(r"\[(\w)\]", key)
    }
    assert listed == registered
    assert "Ctrl+K" not in MAIN and '"K"' in MAIN, "K is next-and-previous, not a command bar"
