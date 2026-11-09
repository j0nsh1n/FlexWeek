"""Settings in the words a student looks for: what each page and control is called, which page holds
it, and what kind of control it is (a switch for on or off, a segmented control for two to four
choices, the designs as pictures). Where things sit and how they are drawn is in the pictures
(pictures/screens_settings_h3.py)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QWidget,
)

from desktop.native.layouts.dialog import DesignPicker
from desktop.native.look import look_menu_token
from desktop.native.settings import FINE_TUNE_LOOK
from desktop.native.update import WINDOWS_SETUP, available
from desktop.native.version import VERSION
from desktop.native.widgets import ChoiceCard, Segmented, Switch
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_settings_pages import label_for, page, prefs
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811

TIMELINE = {"main": "timeline", "day": "one", "options": {}}


def test_this_build_says_its_version_and_is_offered_only_a_newer_release(
    qapp: QApplication, window: NativeWindow
) -> None:
    major, minor, patch = (int(part) for part in VERSION.split("."))
    newer = f"{major}.{minor}.{patch + 1}"
    release = {
        "tag_name": "v0.19.2",
        "assets": [
            {"name": name, "browser_download_url": f"https://example.invalid/{name}"}
            for name in (WINDOWS_SETUP, WINDOWS_SETUP + ".sha256")
        ],
    }
    assert available(release, "windows") is None
    assert available({**release, "tag_name": "v1.0.0"}, "windows") is None
    assert available({**release, "tag_name": "v1.1.0"}, "windows") is None
    assert available({**release, "tag_name": "v1.1.1"}, "windows") is None
    assert available({**release, "tag_name": f"v{VERSION}"}, "windows") is None
    assert available({**release, "tag_name": f"v{newer}"}, "windows")["version"] == newer
    dialog = prefs(window)
    assert dialog.findChild(QLabel, "prefsVersion").text() == f"FlexWeek {VERSION}"


def test_appearance_names_the_design_the_look_the_text_size_and_says_what_a_design_is(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window, TIMELINE)
    appearance = page(dialog, 0)
    assert appearance.findChildren(QGroupBox) == [], "no box inside the page's box"
    shown = {label.text() for label in appearance.findChildren(QLabel) if label.isVisibleTo(dialog)}
    assert {"Look", "Text", "Text size", "Your text size stays the same when you change looks."} <= shown
    assert not any("has its own colours" in text for text in shown)
    notes = [label.text() for label in appearance.findChildren(QLabel, "settingsCardNote")]
    design_line = (
        "A design is how FlexWeek lays out your week. Your blocks and homework are the same in every one."
    )
    assert notes.count(design_line) == 1, "Main view says once what a design is"
    main = appearance.findChild(DesignPicker, "layoutMain")
    assert main is not None and main.cards
    assert main.accessibleName() == "Main view"
    # The design and its looks, the colours that fine-tune them, the day screen and Animations are all
    # on this page.
    for part in (dialog.look, dialog.fine_tune, dialog.motion, appearance.findChild(QWidget, "layoutDay")):
        assert appearance.isAncestorOf(part)


def test_every_heading_on_appearance_is_there(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window, {"main": "classic", "day": "one", "options": {}})
    appearance = page(dialog, 0)
    names = ("prefsHeading", "layoutMainHeading", "layoutDayHeading")
    headings = [
        label.text()
        for label in appearance.findChildren(QLabel)
        if label.objectName() in names and label.isVisibleTo(dialog)
    ]
    assert sorted(headings) == sorted(["Text", "Main view", "Colours", "Day screen", "Every screen"])


def test_focus_says_what_the_long_break_counts(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window)
    assert label_for(dialog.long_every) == "Long break after"
    assert dialog.long_every.text() == "4 focus sessions"
    assert label_for(dialog.long_break) == "Long break minutes"


def test_the_study_hours_card_and_its_button_use_one_name(qapp: QApplication, window: NativeWindow) -> None:
    """The card said "Study hours" but sent the student to "Availability…"; the More item and the
    sheet's title said it too."""
    dialog = prefs(window)
    card = page(dialog, 1)
    lines = [label.text() for label in card.findChildren(QLabel)]
    assert "Choose when FlexWeek may plan homework, including hours kept for one class." in lines
    assert dialog.findChild(QPushButton, "prefsAvailability").text() == "Study hours"
    assert window.findChild(QPushButton, "availabilityButton").text() == "Study hours"


def test_account_has_its_own_row_and_study_hours_is_under_planning(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    account = dialog.findChild(QPushButton, "prefsAccount")
    availability = dialog.findChild(QPushButton, "prefsAvailability")
    assert account.text() == "Manage account…"
    assert label_for(account) == "Account"
    assert page(dialog, 4).isAncestorOf(account)
    assert availability.text() == "Study hours"
    assert page(dialog, 1).isAncestorOf(availability), "Availability is about when to plan"
    asked: list[str] = []
    # The window's own answer is a dialog that waits for a click; only the request is under test.
    dialog.availability_requested.disconnect(window._open_availability)
    dialog.availability_requested.connect(lambda: asked.append("availability"))
    availability.click()
    assert asked == ["availability"]


def test_play_that_hears_nothing_says_what_to_do(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It said "No sound card" and nothing else, and at volume 0 it blamed the computer."""
    dialog = prefs(window)
    next_step = (
        "No sound played. Check that Volume is above 0 % and that your speakers or headphones are "
        "connected and not muted, then press Play again."
    )
    dialog.volume.setValue(0)
    dialog.play_tone.click()
    assert dialog.save_state.text() == next_step
    dialog.save_state.setText("")
    monkeypatch.setattr(dialog._tone_bell, "once", lambda _tone, _volume: False)
    dialog.volume.setValue(80)
    dialog.play_tone.click()
    assert dialog.save_state.text() == next_step


def test_the_look_is_fine_tuned_in_the_colours_card_under_a_name_of_its_own(
    qapp: QApplication, window: NativeWindow
) -> None:
    """"Fine-tune this look" and "Fine-tune this design" read as one toggle, and the look's fine-tuning
    sat under Every screen."""
    dialog = prefs(window)
    colours = dialog.colours_card
    assert dialog.fine_tune.parentWidget() is not None and colours.isAncestorOf(dialog.fine_tune)
    names = {box.text() for box in page(dialog, 0).findChildren(QCheckBox) if box.isVisibleTo(dialog)}
    assert FINE_TUNE_LOOK in names and "Fine-tune this design" not in names
    assert "Show more options for this design" in names


def test_on_or_off_is_a_switch_and_two_to_four_choices_are_side_by_side(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Toggles for on and off, segmented controls for two or three choices, and the drop-down kept for
    the lists too long to lay side by side. Animations' four short levels are side by side too."""
    dialog = prefs(window)
    boxes = [box for box in dialog.findChildren(QCheckBox) if not box.objectName().startswith("alarmDay")]
    assert boxes and all(isinstance(box, Switch) for box in boxes), [
        box.objectName() for box in boxes if not isinstance(box, Switch)
    ]
    spacing = dialog.knobs["density"]
    assert isinstance(spacing, Segmented)
    assert [button.text() for button in spacing.buttons()] == ["Comfortable", "Compact"]
    assert label_for(spacing) == "Spacing"
    for control in (dialog.preferred_view, dialog.drag_step, *dialog.knobs.values()):
        assert isinstance(control, Segmented) and 2 <= control.count() <= 3, control.objectName()
    assert isinstance(dialog.motion, Segmented) and dialog.motion.count() == 4
    # A design's colours stay a list: each design adds its own, and Match my look comes last.
    for box in dialog.findChildren(QComboBox):
        assert box.count() > 3 or box.objectName().endswith("-colour"), box.objectName()
    # A click on a segment is a change, said and saved like any other.
    said: list[bool] = []
    dialog.changed.connect(lambda: said.append(True))
    spacing.buttons()[1].click()
    assert spacing.currentData() == "compact" and said
    assert dialog.look_choice()["knobs"].get("density") == "compact"


def test_animations_has_four_levels_and_follows_the_look_until_one_is_chosen(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Normal, More, Reduce and Off, kept as the ids saved preferences and custom looks already use, and
    Paper starts at Reduce. Settings used to save whatever it showed, so the first change anywhere in
    Settings pinned the level and a look chosen after it could not set it."""
    dialog = prefs(window)
    motion = dialog.motion
    assert [button.text() for button in motion.buttons()] == ["Normal", "More", "Reduce", "Off"]
    assert [motion.itemData(index) for index in range(motion.count())] == ["normal", "extra", "reduce", "off"]
    assert dialog.updates()["motion"] is None, "never chosen: the look's own"
    dialog.look.setCurrentIndex(dialog.look.findData(look_menu_token("preset", "paper")))
    assert motion.currentData() == "reduce", "Paper starts at Reduce"
    assert dialog.updates()["motion"] is None
    motion.buttons()[1].click()
    assert dialog.updates()["motion"] == "extra"
    dialog.look.setCurrentIndex(dialog.look.findData(look_menu_token("preset", "ink")))
    assert motion.currentData() == "extra", "once chosen, the level stays whatever the look"


def test_every_main_view_is_a_picture_with_a_single_name_and_the_experimental_ones_say_so(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.tests.waiting import wait_until

    dialog = prefs(window, TIMELINE)
    appearance = page(dialog, 0)
    picker = appearance.findChild(QWidget, "layoutMain")
    cards = picker.findChildren(ChoiceCard)
    assert [card.accessibleName() for card in cards] == [
        "Today's app",
        "Timeline",
        "Mission control",
        "Bento",
        "Retro desktop",
        "Clay deck",
    ]
    tagged = [card.accessibleName() for card in cards if card.findChild(QLabel, "setupChoiceTag")]
    assert tagged == ["Mission control", "Bento", "Retro desktop", "Clay deck"]
    # The pictures are drawn once Settings would have slid in, one at a time.
    wait_until(
        qapp,
        lambda: all(not card.picture.pixmap().isNull() for card in cards),
        10.0,
        what="each design card shows its picture",
    )
    assert appearance.findChild(QPushButton, "layoutMainReset").isVisibleTo(dialog)
    cards[3].chosen.emit()
    assert dialog.layout_choice()["main"] == "bento"
    assert [card.is_selected() for card in cards] == [False, False, False, True, False, False]
