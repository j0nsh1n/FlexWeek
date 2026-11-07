"""Choosing a look in Settings: Light, Dark and System, the More looks pictures, Your looks, the accent,
Material as one more card, the High contrast suggestions, and how the Retro design colours the page.

What a card or the page looks like (rings, badges, 160 px pictures, contrast of the words) is in the
pictures (pictures/screens_settings_h3.py)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native import settings as settings_module
from desktop.native.layouts.registry import LAYOUTS, MATCH, tokens_for
from desktop.native.layouts.retro import scheme as retro_scheme
from desktop.native.look import look_menu_token
from desktop.native.widgets import ChoiceCard, Segmented, Swatches
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_settings_pages import palette_of, prefs, tile, visible_words
from desktop.tests.window_support import qapp, still  # noqa: F401

# ruff: noqa: F811

MORE = [
    "High contrast",
    "Nocturne",
    "Slate",
    "Poster",
    "Terminal",
    "Paper",
    "Ink",
    "Pastel",
    "Material",
]
HIGH_CONTRAST = look_menu_token("preset", "high-contrast")


def apply(qapp: QApplication, window: NativeWindow) -> None:
    """Let a change to the look reach every widget and end the fades it started."""
    for _ in range(20):
        qapp.processEvents()
    still(window)


def test_more_looks_is_a_grid_of_named_pictures(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window)
    assert [card.accessibleName() for card in dialog.look.more.cards] == MORE
    assert all(not card.picture.pixmap().isNull() for card in dialog.look.more.cards)
    assert dialog.look.more.columns() > 1, "a grid, not one long column"


def test_light_dark_or_system_and_the_other_looks_are_under_more_looks(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    main = dialog.findChild(Segmented, "prefThemeMain")
    more = dialog.look.more
    assert [button.text() for button in main.buttons()] == ["Light", "Dark", "System"]
    shown = [card.accessibleName() for card in more.cards]
    assert "High contrast" in shown and "Nocturne" in shown
    assert not {"Light", "Dark", "System"} & set(shown)
    next(card for card in more.cards if card.accessibleName() == "Nocturne").chosen.emit()
    assert dialog.updates()["theme_pack"] == "nocturne"
    assert not any(button.isChecked() for button in main.buttons()), "no segment claims Nocturne"
    main.buttons()[1].click()
    assert dialog.updates()["theme_pack"] == "dark-frost"
    assert not any(card.is_selected() for card in more.cards), "no picture is marked once Dark is"


def test_one_click_wears_a_look_and_marks_it_and_says_so_inside_the_card(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    assert dialog.look.worn.isHidden(), "Light is worn: the segment shows it"
    tile(dialog, "Nocturne").chosen.emit()
    qapp.processEvents()
    assert dialog.look.currentData() == "pack:nocturne"
    worn = tile(dialog, "Nocturne")
    assert worn.is_selected()
    assert worn.accessibleName() == "Nocturne, selected"
    assert [card.is_selected() for card in dialog.look.more.cards].count(True) == 1
    assert dialog.look.main.currentIndex() == -1, "Light, Dark and System show none"
    assert dialog.look.worn.isHidden(), "the card says it, inside itself, not a line under the grid"
    assert worn.note.text() == "Current"
    assert "Current" in visible_words(worn)
    for other in dialog.look.more.cards:
        if other is not worn:
            assert "Current" not in visible_words(other)
    dialog.look.main.buttons()[0].click()
    assert not any(card.is_selected() for card in dialog.look.more.cards)
    assert dialog.look.worn.isHidden()


def test_a_look_can_be_chosen_from_the_keyboard(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window)
    card = tile(dialog, "Paper")
    assert card.focusPolicy() == Qt.FocusPolicy.StrongFocus
    QTest.keyClick(card, Qt.Key.Key_Space)
    assert dialog.look.currentText() == "Paper" and card.is_selected()


def test_arrows_home_and_end_move_between_look_cards_without_wearing_one(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The cards are one group to the keyboard. Arrows and Home/End move the focus; only Space or Enter
    wears a look."""
    dialog = prefs(window)
    cards = dialog.look.more.cards
    worn = dialog.look_choice()
    cards[0].setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(cards[0], Qt.Key.Key_Right)
    assert cards[1].hasFocus()
    QTest.keyClick(cards[1], Qt.Key.Key_End)
    assert cards[-1].hasFocus()
    QTest.keyClick(cards[-1], Qt.Key.Key_Home)
    assert cards[0].hasFocus()
    assert dialog.look_choice() == worn


def test_look_cards_announce_their_position_and_which_is_worn(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    card = next(card for card in dialog.look.more.cards if card.accessibleName() == "High contrast")
    where = f"{dialog.look.more.cards.index(card) + 1} of {len(dialog.look.more.cards)}"
    assert card.accessibleDescription() == where
    card.chosen.emit()
    assert card.accessibleName() == "High contrast, selected"
    assert card.accessibleDescription() == where
    assert card.note.text() == "Current"


def test_your_looks_follow_the_ten_under_their_own_heading(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window)
    assert dialog.look.yours_heading.isHidden() and dialog.look.yours.isHidden()
    dialog.look.set_saved([{"name": "Night study", "base": "light"}, {"name": "Bus", "base": "dark"}])
    assert [card.accessibleName() for card in dialog.look.yours.cards] == ["Night study", "Bus"]
    assert dialog.look.yours_heading.text() == "Your looks"
    assert not dialog.look.yours_heading.isHidden()
    dialog.look.set_saved([])
    assert dialog.look.yours.cards == [] and dialog.look.yours_heading.isHidden()


def test_light_dark_and_system_say_which_is_worn_and_the_line_goes_when_a_picture_is(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    segments = dialog.look.main.buttons()
    segments[2].click()
    qapp.processEvents()
    line = dialog.look.main_worn
    assert line.text() == "Wearing System" and line.isVisibleTo(dialog)
    tile(dialog, "Nocturne").chosen.emit()
    qapp.processEvents()
    assert line.text().strip() == ""


def test_the_look_button_and_the_design_description_have_their_words(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    assert dialog.findChild(QPushButton, "prefCustomise").text() == "Edit look…"
    sentence = "The week grid with the sidebar. Its colours come from the look you choose above."
    assert LAYOUTS["classic"].summary == sentence
    card = next(card for card in dialog.findChildren(ChoiceCard) if card.accessibleName() == "Today's app")
    assert card.note.text() == sentence


def test_the_accent_is_swatches_in_the_looks_own_colours(qapp: QApplication, window: NativeWindow) -> None:
    dialog = prefs(window)
    swatches = dialog.findChild(Swatches, "prefAccent")
    assert [button.text() for button in swatches.buttons()] == ["Blue", "Sky", "Gold", "Sea", "Sand"]
    sea = swatches.buttons()[3]
    sea.click()
    qapp.processEvents()
    assert dialog.updates()["accent"] == "sea" and sea.isChecked()


def test_customise_has_its_row_under_look_and_opens_the_look_editor(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    button = dialog.findChild(QPushButton, "prefCustomise")
    label = dialog.colours_card.layout().labelForField(button)
    assert isinstance(label, QLabel) and label.text() == "Your own look"
    assert button.isEnabled() and button.toolTip()
    button.click()
    qapp.processEvents()
    editor = dialog.findChild(QWidget, "lookEditor")
    assert editor is not None and editor.isVisible()
    assert not dialog.nav.isVisible(), "Settings' own list is put away under it"


def test_high_contrast_says_it_keeps_its_own_yellow_and_black(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window, size=(1024, 640))
    note = dialog.accent_note
    assert not note.isVisibleTo(dialog)
    dialog.look.setCurrentIndex(dialog.look.findData(HIGH_CONTRAST))
    qapp.processEvents()
    assert note.isVisibleTo(dialog)
    palette = dialog.shown_palette()
    assert palette["window"] == "#000000"
    assert palette["accent"] == "#ffd400"
    done = dialog.findChild(QPushButton, "settingsDone")
    assert done is not None and done.isVisibleTo(dialog)


def test_high_contrast_names_its_text_suggestion_and_the_button_says_what_it_does(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    spoken: list[str] = []
    monkeypatch.setattr(settings_module, "announce", lambda _widget, words, **_kw: spoken.append(words))
    dialog = prefs(window)
    dialog.look.setCurrentIndex(dialog.look.findData("preset:high-contrast"))
    qapp.processEvents()
    assert dialog.text_suggest.isVisibleTo(dialog)
    words = [label.text() for label in dialog.text_suggest.findChildren(QLabel)]
    assert words == ["High contrast is easiest to read with Large text."]
    use = dialog.findChild(QPushButton, "prefTextSuggestUse")
    assert use.text() == "Use Large text"
    notes = [label.text() for label in dialog.findChildren(QLabel, "settingsCardNote")]
    assert "Your text size stays the same when you change looks." in notes
    assert dialog.knobs["text"].currentData() == "normal"
    use.click()
    qapp.processEvents()
    assert dialog.knobs["text"].currentData() == "large"
    assert spoken == ["Text size is now Large."]


def test_a_curated_canvas_look_does_not_leave_a_custom_look_marked_selected(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.native.custom_look import save_look, start_custom, wear

    dialog = prefs(window)
    dialog.saved_looks = save_look([], start_custom(dialog._pack, dialog._look), "My custom look")
    dialog._look = wear(dialog._look, dialog.saved_looks[0])
    dialog._show_look()
    assert dialog.look.currentData() == "saved:My custom look"

    dialog.layout_sections[0].pick.setCurrentIndex(dialog.layout_sections[0].pick.findData("bento"))

    assert dialog.layout_sections[0].values()["look"] == "preset:bento-indigo"
    assert dialog.look.currentData() is None
    assert dialog.look.worn.text() == "Wearing Indigo"
    assert dialog.look.findData("saved:My custom look") != dialog.look.currentIndex()


def test_general_look_choice_sets_both_layouts_to_your_look(
    qapp: QApplication, window: NativeWindow
) -> None:
    dialog = prefs(window)
    dialog.look.setCurrentIndex(dialog.look.findData(HIGH_CONTRAST))
    assert [section.values()["look"] for section in dialog.layout_sections] == ["your", "your"]


def test_material_is_one_more_card_and_choosing_it_wears_material(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Material sits in the Look grid as one more card; choosing it switches to Material, and it says
    Current while the Material window is the one worn."""
    dialog = prefs(window)
    material = dialog.look.material
    assert material.accessibleName() == "Material"
    assert material.note.text() == " "
    material.chosen.emit()
    for _ in range(10):
        qapp.processEvents()
    assert window._stack.currentWidget().objectName() == "materialPage"
    assert material.note.text() == "Current"
    assert not any(card.is_selected() for card in dialog.look.more.cards if card is not material)
    window._use_widgets_styles()
    for _ in range(10):
        qapp.processEvents()
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert material.note.text() == " "


def test_choosing_material_again_retries_a_failed_open_and_current_follows_the_landing(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Activating the Material card always asks to open Material, even when the hidden toggle is
    already checked, so a failed open can be retried. Current follows whether Material opened."""
    dialog = prefs(window)
    host = window._ensure_material()
    assert host is not None
    material = dialog.look.material
    host.break_load = True
    material.chosen.emit()
    for _ in range(20):
        qapp.processEvents()
    assert window._stack.currentWidget().objectName() == "weekPage"
    assert material.note.text() != "Current"
    host.break_load = False
    material.chosen.emit()
    for _ in range(20):
        qapp.processEvents()
    assert window._stack.currentWidget().objectName() == "materialPage"
    assert material.note.text() == "Current"


def test_material_is_not_current_after_a_late_failure_or_a_rebuilt_settings_page(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Material that opens and then fails, and a Settings page built after a failed open, both leave
    the Material card not Current while the Widgets week is up."""
    dialog = prefs(window)
    host = window._ensure_material()
    assert host is not None
    dialog.look.material.chosen.emit()
    for _ in range(20):
        qapp.processEvents()
    assert window._stack.currentWidget().objectName() == "materialPage"
    host._on_scene_graph_error(None, "the graphics device was lost")
    for _ in range(20):
        qapp.processEvents()
    assert window._material_gave_up is True
    window._open_settings()
    for _ in range(5):
        qapp.processEvents()
    assert window._settings.look.material.note.text() != "Current"
    window._discard_settings_page()
    window._attach_settings_page(window._build_settings_page())
    assert window._settings.look.material.note.text() != "Current"


def test_retro_gives_the_settings_text_its_own_ink_whatever_look_is_worn(
    qapp: QApplication, window: NativeWindow
) -> None:
    """With the Retro design, Settings takes Retro's ink for its text, not the worn look's heading
    colours, so Dark plus Retro still reads. High contrast stays High contrast, and leaving Retro
    gives the worn look's ink back."""

    def ink(label: QLabel) -> str:
        label.ensurePolished()
        return label.palette().color(QPalette.ColorRole.WindowText).name()

    def retro_ink() -> str:
        return retro_scheme(tokens_for("retro", MATCH, palette_of(window))).ink

    window.session.preferences = {**(window.session.preferences or {}), "motion": "off"}
    window._apply_appearance()
    dialog = prefs(window, size=(1280, 800))
    heading = next(label for label in dialog.findChildren(QLabel, "prefsHeading") if label.text() == "Text")
    body = next(label for label in heading.parentWidget().findChildren(QLabel) if label.text() == "Text size")
    dialog.look.main.buttons()[1].click()
    apply(qapp, window)
    worn_heading, worn_body = ink(heading), ink(body)

    main = dialog.layout_sections[0]
    main.pick.setCurrentIndex(main.pick.findData("retro"))
    apply(qapp, window)
    # Dark after Retro rebuilds the look sheet on Retro's cards; Dark then Retro alone keeps Retro's own
    # ink and misses the worn heading colours.
    dialog.look.main.buttons()[0].click()
    apply(qapp, window)
    dialog.look.main.buttons()[1].click()
    apply(qapp, window)
    assert ink(heading) == retro_ink()
    assert ink(body) == retro_ink()

    dialog.look.setCurrentIndex(dialog.look.findData(HIGH_CONTRAST))
    apply(qapp, window)
    assert ink(heading) == retro_ink()

    dialog.look.main.buttons()[1].click()
    apply(qapp, window)
    main.pick.setCurrentIndex(main.pick.findData("classic"))
    apply(qapp, window)
    assert ink(heading) == worn_heading
    assert ink(body) == worn_body
