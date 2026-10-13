"""Settings in the 0.17 system (decision 24 of docs/0.17/plan.md, look-review.md section 8).

The cards stood at 760 pixels against the left with a quarter of the window empty; the section list
was plain words; Look was one long dropdown and Accent another; the number boxes were four widths;
and the cards ran on under the footer with nothing to end them.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSpinBox, QWidget

from desktop.native import settings as settings_module
from desktop.native.look import ACCENT_COLORS, look_menu_token, resolved_palette
from desktop.native.settings import SETTINGS_COLUMN, SettingsPage
from desktop.native.tokens import contrast
from desktop.native.widgets import Segmented, Swatches, Switch
from desktop.native.window import NativeWindow
from desktop.tests.window_support import qapp, server, signed_out, window  # noqa: F401


def open_settings(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    size: tuple[int, int] = (1280, 800),
) -> SettingsPage:
    window.resize(*size)
    window._open_settings()
    page = window._settings
    for _ in range(10):
        qapp.processEvents()
    return page


def palette_of(window: NativeWindow) -> dict:  # noqa: F811
    pack, dark, accent = window._look_inputs()
    return resolved_palette(pack, dark, window._look, accent)


def test_the_column_of_cards_is_centred_up_to_960(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    page = open_settings(qapp, window, (1600, 900))
    area = page.stack.currentWidget()
    body = area.widget()
    items = [body.layout().itemAt(index) for index in range(body.layout().count())]
    column = next(item.widget() for item in items if item.widget() is not None)
    assert column.width() == SETTINGS_COLUMN == 960
    left = column.mapTo(area.viewport(), QPoint(0, 0)).x()
    right = area.viewport().width() - left - column.width()
    assert abs(left - right) <= 2, (left, right)
    page.close_page()


def test_each_section_has_its_icon_and_the_chosen_one_an_accent_bar(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page = open_settings(qapp, window)
    nav = page.nav
    assert all(not nav.item(row).icon().isNull() for row in range(nav.count()))
    accent = QColor(palette_of(window)["accent"])
    picture = nav.viewport().grab().toImage()
    for row in range(nav.count()):
        box = nav.visualItemRect(nav.item(row))
        edge = picture.pixelColor(box.left() + 1, box.center().y())
        assert (edge == accent) == (row == nav.currentRow()), row
    page.close_page()


def test_look_is_light_dark_or_system_and_the_other_looks_are_under_more_looks(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    page = open_settings(qapp, window)
    main = page.findChild(Segmented, "prefThemeMain")
    more = page.look.more
    assert [button.text() for button in main.buttons()] == ["Light", "Dark", "System"]
    shown = [card.accessibleName() for card in more.cards]
    assert "High contrast" in shown and "Nocturne" in shown
    assert not {"Light", "Dark", "System"} & set(shown)
    next(card for card in more.cards if card.accessibleName() == "Nocturne").chosen.emit()
    assert page.updates()["theme_pack"] == "nocturne"
    assert not any(button.isChecked() for button in main.buttons()), "no segment claims Nocturne"
    main.buttons()[1].click()
    assert page.updates()["theme_pack"] == "dark-frost"
    assert not any(card.is_selected() for card in more.cards), "no picture is marked once Dark is"
    page.close_page()


def test_look_cards_announce_selection_position_and_wearing_badge(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:  # noqa: F811
    page = open_settings(qapp, window)
    card = next(card for card in page.look.more.cards if card.accessibleName() == "High contrast")
    assert (
        card.accessibleDescription()
        == f"{page.look.more.cards.index(card) + 1} of {len(page.look.more.cards)}"
    )
    card.chosen.emit()
    assert card.accessibleName() == "High contrast, selected"
    assert (
        card.accessibleDescription()
        == f"{page.look.more.cards.index(card) + 1} of {len(page.look.more.cards)}"
    )
    assert card.note.text() == "Wearing"
    # The page redraws what its style sheet cannot (the badge's colours) on the next turn of the event loop.
    qapp.processEvents()
    # The badge is a 24 px circle 10 px down and 12 px in from the card's top right, with a 16 px check in
    # its middle. Sampled on the circle around the check, on all four sides; the preview picture under it
    # must not be the accent at all four, or the check would pass without a badge.
    accent = palette_of(window)["accent"]
    w = card.width()
    ring = [(w - 34, 22), (w - 24, 12), (w - 14, 22), (w - 24, 32)]
    worn = card.grab().toImage()
    assert [worn.pixelColor(x, y).name() for x, y in ring] == [accent] * 4
    card.select(False)
    plain = card.grab().toImage()
    assert any(plain.pixelColor(x, y).name() != accent for x, y in ring)
    card.select(True)
    page.close_page()


def test_a_look_card_reached_by_keyboard_has_a_ring_outside_its_face(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """N14/Q8: the focused card gets a 2 px ring with a 2 px gap outside its face, reading at 3 to 1 on what
    is behind it; a click gives no ring."""
    page = open_settings(qapp, window)
    grid = page.look.more
    grid.ensurePolished()

    def column(card: QWidget) -> tuple[QColor, QColor, QColor]:
        qapp.processEvents()
        picture = grid.grab().toImage()
        middle = card.y() + card.height() // 2
        # 4 px out is the ring's middle, 1 px out the gap, 9 px out the background between cards.
        return tuple(picture.pixelColor(card.x() - out, middle) for out in (4, 1, 9))

    tabbed, clicked = grid.cards[1], grid.cards[2]
    tabbed.setFocus(Qt.FocusReason.TabFocusReason)
    ring, gap, behind = column(tabbed)
    assert contrast(ring.name(), behind.name()) >= 3.0, (ring.name(), behind.name())
    assert gap.name() == behind.name()
    clicked.setFocus(Qt.FocusReason.MouseFocusReason)
    for card in (tabbed, clicked):
        edge, _, ground = column(card)
        assert edge.name() == ground.name()
    page.close_page()


def test_arrows_home_and_end_move_between_look_cards_without_wearing_one(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """N14: the cards are one group to the keyboard. Arrows and Home/End move the focus; only Space or Enter
    wears a look."""
    page = open_settings(qapp, window)
    cards = page.look.more.cards
    worn = page.look_choice()
    cards[0].setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(cards[0], Qt.Key.Key_Right)
    assert cards[1].hasFocus()
    QTest.keyClick(cards[1], Qt.Key.Key_End)
    assert cards[-1].hasFocus()
    QTest.keyClick(cards[-1], Qt.Key.Key_Home)
    assert cards[0].hasFocus()
    assert page.look_choice() == worn
    page.close_page()


def test_the_accent_is_swatches_in_the_looks_own_colours(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    page = open_settings(qapp, window)
    swatches = page.findChild(Swatches, "prefAccent")
    assert [button.text() for button in swatches.buttons()] == ["Blue", "Sky", "Gold", "Sea", "Sand"]
    sea = swatches.buttons()[3]
    sea.click()
    for _ in range(5):
        qapp.processEvents()
    assert page.updates()["accent"] == "sea" and sea.isChecked()
    axis = palette_of(window)["axis"]
    picture = sea.grab().toImage()
    ring = sea.SIZE + 8
    edge = QPoint(sea.width() // 2 - sea.SIZE // 2 + 3, ring // 2)
    assert picture.pixelColor(edge).name() == ACCENT_COLORS["sea"][axis][0]
    page.close_page()


def test_tab_to_the_last_switch_on_look_scrolls_it_above_the_footer(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """Q9: the footer covers the bottom of the page, and a switch focused by Tab under it could not be
    seen. Focus scrolls the section so the switch ends above the footer."""
    page = open_settings(qapp, window)
    area = page.stack.widget(0)
    switches = area.widget().findChildren(Switch)
    last = max(switches, key=lambda switch: switch.mapTo(area.widget(), QPoint(0, 0)).y())
    bar = area.verticalScrollBar()
    bar.setValue(0)
    window.activateWindow()
    qapp.setActiveWindow(window)
    for _ in range(5):
        qapp.processEvents()
    last.setFocus()
    for _ in range(5):
        qapp.processEvents()
    assert qapp.focusWidget() is last, "the switch did not take the focus, so this proves nothing"
    assert bar.maximum() > 0, "the section does not run under the footer, so this proves nothing"
    top = last.mapTo(page, QPoint(0, 0)).y()
    footer_top = page.footer.mapTo(page, QPoint(0, 0)).y()
    assert top + last.height() <= footer_top, (top + last.height(), footer_top)
    page.close_page()


def test_customise_has_its_row_under_look_and_opens_the_look_editor(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    """Plan, "Customise": B, the look editor, full window over Settings."""
    page = open_settings(qapp, window)
    button = page.findChild(QPushButton, "prefCustomise")
    label = page.colours_card.layout().labelForField(button)
    assert isinstance(label, QLabel) and label.text() == "Your own look"
    assert button.isEnabled() and button.toolTip()
    look = page.findChild(QWidget, "prefTheme")
    assert button.mapTo(page, QPoint(0, 0)).y() > look.mapTo(page, QPoint(0, 0)).y()
    button.click()
    for _ in range(10):
        qapp.processEvents()
    editor = page.findChild(QWidget, "lookEditor")
    assert editor is not None and editor.isVisible()
    assert editor.geometry() == page.rect(), "the editor fills the page"
    assert not page.nav.isVisible(), "Settings' own list is put away under it"
    page.close_page()


def test_every_number_box_on_a_page_is_one_width(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """Focus's boxes were 30, 15, 30 and "4 focus sessions" wide, each sized to its text."""
    page = open_settings(qapp, window)
    page.nav.setCurrentRow(2)
    for _ in range(5):
        qapp.processEvents()
    focus = page.stack.currentWidget().widget()
    widths = [box.width() for box in focus.findChildren(QSpinBox)]
    assert len(widths) >= 4 and len(set(widths)) == 1, widths
    page.close_page()


def test_a_hairline_ends_the_page_above_the_footer(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    page = open_settings(qapp, window)
    footer = page.findChild(QWidget, "settingsFooter")
    picture = footer.grab().toImage()
    assert picture.pixelColor(footer.width() // 2, 0).name() == palette_of(window)["hairline"]
    page.close_page()


def test_high_contrast_says_it_keeps_its_own_yellow(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    page = open_settings(qapp, window)
    note = page.accent_note
    assert not note.isVisibleTo(page)
    page.look.setCurrentIndex(page.look.findData(look_menu_token("preset", "high-contrast")))
    for _ in range(5):
        qapp.processEvents()
    assert note.isVisibleTo(page)
    page.close_page()


def test_high_contrast_names_its_text_suggestion_and_the_button_says_what_it_does(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-W10 and N13-A31: "Suggests Large text" with a bare "Use", and "Kept for every look."."""
    spoken: list[str] = []
    monkeypatch.setattr(settings_module, "announce", lambda _widget, words, **_kw: spoken.append(words))
    page = open_settings(qapp, window)
    box = page.look
    box.setCurrentIndex(box.findData("preset:high-contrast"))
    qapp.processEvents()
    assert page.text_suggest.isVisibleTo(page)
    words = [label.text() for label in page.text_suggest.findChildren(QLabel)]
    assert words == ["High contrast is easiest to read with Large text."]
    use = page.findChild(QPushButton, "prefTextSuggestUse")
    assert use.text() == "Use Large text"
    notes = [label.text() for label in page.findChildren(QLabel, "settingsCardNote")]
    assert "Your text size stays the same when you change looks." in notes
    assert page.knobs["text"].currentData() == "normal"
    use.click()
    qapp.processEvents()
    assert page.knobs["text"].currentData() == "large"
    assert spoken == ["Text size is now Large."]
    page.close_page()
