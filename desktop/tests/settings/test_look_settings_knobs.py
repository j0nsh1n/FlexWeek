"""The look boxes in Settings: choosing a look puts its knobs in the boxes, a knob moved by hand stays,
a look of the student's own shows what it sets and leaves changes to Customise, and the keyboard
reaches Light, Dark and System when a More looks card is worn."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox

from desktop.native.look import (
    LOOK_DEFAULTS,
    effective_look,
    look_menu_token,
    preset_knobs,
)
from desktop.native.settings import (
    OWN_LOOK_ACCENT_NOTE,
    OWN_LOOK_KNOBS_NOTE,
    SAVED_LOOK,
    SettingsPage,
)
from desktop.tests.window_support import qapp  # noqa: F401


def settings(look: dict) -> SettingsPage:
    return SettingsPage(None, {}, look, {})


def choose(dialog: SettingsPage, token: str) -> None:
    index = dialog.look.findData(token)
    assert index >= 0, token
    dialog.look.setCurrentIndex(index)


def move(dialog: SettingsPage, knob: str, value: str) -> None:
    dialog.knobs[knob].setCurrentIndex(dialog.knobs[knob].findData(value))


def shown(dialog: SettingsPage) -> dict:
    return {knob: box.currentData() for knob, box in dialog.knobs.items()}


def test_settings_opens_on_appearance_with_fine_tune_closed(qapp: QApplication) -> None:  # noqa: F811
    dialog = settings({})
    assert dialog.nav.currentRow() == 0
    assert dialog.fine_host.isHidden() is True
    dialog.fine_tune.setChecked(True)
    assert dialog.fine_host.isHidden() is False


def test_choosing_terminal_in_settings_applies_every_one_of_its_knobs(qapp: QApplication) -> None:  # noqa: F811
    """The dialog once recorded all seven boxes as overrides.

    Terminal then arrived with its colours, round corners and a sans font.
    """
    dialog = settings({"preset": "default", "knobs": {}})
    assert shown(dialog) == LOOK_DEFAULTS
    choose(dialog, look_menu_token("preset", "terminal"))
    assert shown(dialog) == preset_knobs("terminal")
    chosen = dialog.look_choice()
    # Only the text size is saved beside the preset: it is the student's own, whatever the look.
    assert chosen == {"preset": "terminal", "knobs": {"text": "normal"}}
    assert effective_look(chosen) == preset_knobs("terminal")


def test_a_knob_moved_by_hand_stays_when_the_look_changes(qapp: QApplication) -> None:  # noqa: F811
    dialog = settings({"preset": "default", "knobs": {}})
    move(dialog, "corners", "rounded")
    choose(dialog, look_menu_token("preset", "terminal"))
    assert shown(dialog)["corners"] == "rounded"
    assert shown(dialog)["font"] == "mono"
    assert dialog.look_choice() == {"preset": "terminal", "knobs": {"corners": "rounded", "text": "normal"}}
    move(dialog, "depth", "bold")
    assert dialog.look_choice() == {
        "preset": "terminal",
        "knobs": {"corners": "rounded", "depth": "bold", "text": "normal"},
    }
    assert effective_look(dialog.look_choice())["font"] == "mono"
    choose(dialog, look_menu_token("pack", "system"))
    assert shown(dialog)["corners"] == "rounded"
    assert shown(dialog)["depth"] == "bold"
    assert shown(dialog)["font"] == "sans"
    assert dialog.look_choice() == {
        "preset": "default",
        "knobs": {"corners": "rounded", "depth": "bold", "text": "normal"},
    }


def test_opening_settings_shows_the_look_on_screen_and_changes_nothing(qapp: QApplication) -> None:  # noqa: F811
    stored = {"preset": "terminal", "knobs": {"text": "large", "corners": "rounded"}}
    dialog = settings(stored)
    # Each box shows what the student sees, not the first value in its list.
    assert shown(dialog) == {**preset_knobs("terminal"), "text": "large", "corners": "rounded"}
    # Pressing OK untouched must hand back exactly what was stored: the preset connection is made
    # after the stored preset is selected, so opening the dialog never resets a student's own knobs.
    assert dialog.look_choice() == stored
    assert dialog.findChild(QComboBox, "lookPreset") is None
    assert dialog.look.findData(look_menu_token("preset", "terminal")) >= 0
    assert dialog.look.findData(look_menu_token("pack", "system")) >= 0


def test_a_look_of_your_own_shows_what_it_sets_and_leaves_changes_to_customise(
    qapp: QApplication,  # noqa: F811
) -> None:
    """A custom look sets every knob and the accent, so the ones in Settings changed nothing while it
    was worn. They show its values and cannot be changed, and a line says where they can; a built-in
    look hands them back with the knob moved before it was put on."""
    night = {
        "name": "Night study",
        "base": "dark",
        "accent": "sea",
        "spacing": "compact",
        "shadows": "none",
        "body_font": "serif",
    }
    built_in = {"preset": "terminal", "knobs": {}}
    dialog = SettingsPage(None, {"accent": "gold"}, built_in, {}, saved_looks=[night])
    dialog.fine_tune.setChecked(True)
    move(dialog, "corners", "rounded")
    choose(dialog, SAVED_LOOK + "Night study")
    assert shown(dialog) == {
        "surface": "layered",
        "corners": "soft",
        "depth": "none",
        "font": "serif",
        "blocks": "edge",
        "density": "compact",
        "text": "normal",
    }
    assert not any(box.isEnabled() for box in dialog.knobs.values())
    assert dialog.accent.currentData() == "sea" and not dialog.accent.isEnabled()
    assert dialog.own_look_note.isVisibleTo(dialog)
    assert dialog.own_look_note.text() == OWN_LOOK_KNOBS_NOTE.format(name="Night study")
    assert dialog.accent_note.isVisibleTo(dialog)
    assert dialog.accent_note.text() == OWN_LOOK_ACCENT_NOTE.format(name="Night study")
    assert dialog.updates()["accent"] == "gold", "the account's accent stays for the other looks"
    assert dialog.look_choice() == {
        "preset": "terminal",
        "knobs": {"corners": "rounded", "text": "normal"},
        "custom": night,
    }
    choose(dialog, look_menu_token("preset", "paper"))
    assert dialog.look_choice() == {"preset": "paper", "knobs": {"corners": "rounded", "text": "normal"}}
    assert shown(dialog) == {**preset_knobs("paper"), "corners": "rounded"}
    assert all(box.isEnabled() for box in dialog.knobs.values())
    assert dialog.accent.currentData() == "gold" and dialog.accent.isEnabled()
    assert not dialog.own_look_note.isVisibleTo(dialog) and not dialog.accent_note.isVisibleTo(dialog)
    move(dialog, "depth", "bold")
    assert dialog.look_choice() == {
        "preset": "paper",
        "knobs": {"corners": "rounded", "depth": "bold", "text": "normal"},
    }


def test_wearing_a_more_looks_card_leaves_light_dark_system_reachable_by_tab(
    qapp: QApplication,  # noqa: F811
) -> None:
    """A28: with High contrast worn none of the three was a Tab stop, so the keyboard skipped the row."""
    dialog = settings({})
    dialog.look.setCurrentIndex(dialog.look.findData("preset:high-contrast"))
    dialog.show()
    light, dark, system = dialog.look.main.buttons()
    assert dialog.look.main.currentIndex() == -1
    # The Tab stop a student is on just before the row: hidden widgets take no Tab (since 1.0.0 the
    # design's hidden More and Reset sit just before it in the chain).
    before = light.previousInFocusChain()
    while (
        before.focusPolicy() & Qt.FocusPolicy.TabFocus == 0
        or before in (light, dark, system)
        or not before.isVisibleTo(dialog)
    ):
        before = before.previousInFocusChain()
    before.setFocus(Qt.FocusReason.TabFocusReason)
    # The window is not the active one under test, so focus is read from the window, not the application.
    for _ in range(3):
        if dialog.focusWidget() is light:
            break
        dialog.focusNextChild()
    assert dialog.focusWidget() is light
    QTest.keyClick(light, Qt.Key.Key_Right)
    assert dialog.focusWidget() is dark
    QTest.keyClick(dark, Qt.Key.Key_Left)
    QTest.keyClick(light, Qt.Key.Key_Return)
    assert dialog.look.currentData() == "pack:light-frost"
    assert dialog.look.main.currentIndex() == 0
    dialog.close()
