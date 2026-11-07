"""Pictures of the Settings pages: where things sit, how wide they are, the colours and contrast of what is
drawn. These were checks in code (test_settings_0183, test_settings_look, test_settings_finding,
test_settings_words, test_material_settings) and are judged on the picture now."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.layouts.dialog import DesignPicker
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import look_menu_token
from desktop.native.settings import SettingsPage
from desktop.native.widgets import Switch
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.settings.support_material_settings import _bridge, _panel, _show_material
from desktop.tests.settings.support_settings_pages import (
    ALERTS,
    APPEARANCE,
    COMPUTER,
    FOCUS,
    PLANNING,
    page,
    prefs,
    show_section,
    tile,
)

SETTINGS = ("desktop/native/settings.py", "desktop/native/widgets.py", "desktop/native/look.py")
HIGH_CONTRAST = look_menu_token("preset", "high-contrast")


def _pump(times: int = 20) -> None:
    for _ in range(times):
        QApplication.processEvents()


def _section(window: NativeWindow, row: int) -> SettingsPage:
    dialog = prefs(window)
    show_section(dialog, row)
    for picker in dialog.findChildren(DesignPicker):
        picker.warm()
    _pump(5)
    return dialog


def _appearance(window: NativeWindow) -> object:
    _section(window, APPEARANCE)
    return None


def _planning(window: NativeWindow) -> object:
    _section(window, PLANNING)
    return None


def _focus(window: NativeWindow) -> object:
    _section(window, FOCUS)
    return None


def _alerts(window: NativeWindow) -> object:
    dialog = prefs(window)
    dialog.alarm_tone.setCurrentIndex(dialog.alarm_tone.findData("spotify"))
    show_section(dialog, ALERTS)
    return None


def _computer(window: NativeWindow) -> object:
    _section(window, COMPUTER)
    return None


def _footer_with_dark_preview_behind(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    area = dialog.stack.widget(APPEARANCE)
    bar = area.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    _pump(5)
    return None


def _footer_in_high_contrast(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.look.setCurrentIndex(dialog.look.findData(HIGH_CONTRAST))
    _pump(8)
    area = dialog.stack.widget(APPEARANCE)
    area.verticalScrollBar().setValue(area.verticalScrollBar().maximum() // 2)
    _pump(5)
    return None


def _look_cards(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.look.set_saved([{"name": "Night study", "base": "light"}, {"name": "Bus", "base": "dark"}])
    tile(dialog, "Nocturne").chosen.emit()
    _pump(8)
    return dialog.look


def _look_card_focus(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.look.more.cards[1].setFocus(Qt.FocusReason.TabFocusReason)
    _pump(5)
    return dialog.look.more


def _look_pictures(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.look.set_saved([{"name": "Night study", "base": "light", "colours": {"page": "#262d3b"}}])
    _pump(8)
    return dialog.look


def _light_dark_system(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.look.main.buttons()[2].click()
    _pump(5)
    return dialog.look


def _design_cards(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    return page(dialog, APPEARANCE).findChild(DesignPicker, "layoutMain")


def _high_contrast_cards_at_large_text(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.look.setCurrentIndex(dialog.look.findData(HIGH_CONTRAST))
    text = dialog.knobs["text"]
    text.setCurrentIndex(text.findData("large"))
    _pump(8)
    return dialog.look.more


def _sidebar(window: NativeWindow) -> object:
    dialog = _section(window, PLANNING)
    return dialog.nav


def _swatches(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.findChild(QWidget, "prefAccent").buttons()[3].click()
    _pump(5)
    return dialog.findChild(QWidget, "prefAccent")


def _look_editor_open(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    dialog.findChild(QPushButton, "prefCustomise").click()
    _pump(10)
    return None


def _last_switch_focused(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    area = dialog.stack.widget(APPEARANCE)
    switches = area.widget().findChildren(Switch)
    last = max(switches, key=lambda switch: switch.mapTo(area.widget(), switch.rect().topLeft()).y())
    area.verticalScrollBar().setValue(0)
    last.setFocus()
    _pump(5)
    return None


def _retro(window: NativeWindow, dark: bool) -> object:
    window.session.preferences = {**(window.session.preferences or {}), "motion": "off"}
    window._layout = sanitize_layout({"main": "retro", "day": "one"})
    window._apply_appearance()
    dialog = prefs(window)
    dialog.look.main.buttons()[1 if dark else 0].click()
    _pump(20)
    return None


def _canvas_follows_look(window: NativeWindow) -> object:
    dialog = _section(window, APPEARANCE)
    main = dialog.layout_sections[0]
    main.pick.setCurrentIndex(main.pick.findData("bento"))
    chosen = dialog.findChild(QWidget, "layoutMain-look")
    chosen.setCurrentIndex(chosen.findData("preset:bento-indigo"))
    _pump(30)
    chosen.setCurrentIndex(chosen.findData(HIGH_CONTRAST))
    _pump(40)
    return window.planner.currentWidget()


def _material_cutoff(window: NativeWindow) -> object:
    window.resize(800, 800)
    _show_material(QApplication.instance(), window)
    window.resize(800, 800)
    _bridge(window).showPage("settings")
    _panel(window).closeAdvanced()
    _panel(window).setSection("planning")
    _pump(30)
    return None


def _availability_cutoff(window: NativeWindow) -> object:
    from desktop.native.widgets import AvailabilityDialog

    dialog = AvailabilityDialog(window, {})
    dialog.show()
    dialog.tabs.setCurrentIndex(dialog.tabs.findData("cutoff"))
    _pump(5)
    return dialog


SCREENS: list[Screen] = [
    Screen(
        id="settings.appearance",
        area="settings",
        prepare=_appearance,
        checks=(
            "The cards stand in one column that is 960 px wide and centred (left and right margins within"
            " 2 px) when the window is wider. Down the page the order is: Look, Text and Text size with its"
            " note (in view without scrolling), the Main view designs, the look and its Colours, the Day"
            " screen, Animations. Headings are bold and the notes under them are plain. The design cards are"
            " painted on the page itself, with no grey band behind them. Reset is an outlined button at the"
            " left, no wider than its words, not a bar across the page. Every field in a form column starts"
            " at the same left edge (text boxes, steppers, drop-downs, buttons and the segmented control's"
            " drawn track, to the pixel), and the label column is one width."
        ),
        sources=SETTINGS,
        main=True,
    ),
    Screen(
        id="settings.planning",
        area="settings",
        prepare=_planning,
        checks=(
            "The Study hours button is outlined, not filled, and no wider than its words or 190 px,"
            " whichever is more. Labels and fields line up in the same two columns as on the other pages."
            " The last control ends above the footer with the page's bottom margin at least the footer's"
            " height."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.focus",
        area="settings",
        prepare=_focus,
        checks=(
            "The timer preset sits first, then the work, break, long break and long break count boxes, top"
            " to bottom. Each of the five controls is exactly 260 px wide, and every number box on the page"
            " is the same width (they were 30, 15, 30 and the width of '4 focus sessions')."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.alerts",
        area="settings",
        prepare=_alerts,
        checks=(
            "With the sound set to Spotify, the lead, volume, sound, Spotify link, alarm name, alarm time,"
            " alarm sound and alarm Spotify controls are all one width, at least 260 px (the widest label,"
            " 'A Spotify song or playlist', sets it). The tray note and 'No alarms yet' are in the muted"
            " grey of the look."
        ),
        sources=SETTINGS,
        main=True,
    ),
    Screen(
        id="settings.computer",
        area="settings",
        prepare=_computer,
        checks=(
            "The values on This computer (preferred view, clock, account, run setup, version, check for"
            " updates) start at the same x as the values on Focus and Alerts. Manage account, Run setup"
            " and Check for updates are three buttons of one width, outlined, as wide as their words and"
            " not wider than 190 px, and each is quieter than Done."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.footer_over_a_dark_preview",
        area="settings",
        prepare=_footer_with_dark_preview_behind,
        checks=(
            "Scrolled so a dark look preview is under the footer's top edge: the footer ends the page"
            " with a hairline in the look's hairline colour and the preview is cut cleanly there. No blurred"
            " cream band mixes into the dark preview above Done (the old 24 px ramp), and the footer's"
            " padding is the page colour, opaque. Footer margins are 32, 12, 32 and 16 px."
        ),
        sources=SETTINGS,
        main=True,
    ),
    Screen(
        id="settings.footer_in_high_contrast",
        area="settings",
        prepare=_footer_in_high_contrast,
        checks=(
            "High contrast keeps its own black page and yellow (#ffd400) accent. The footer stays black"
            " with a hairline in the look's hairline colour and a visible Done button, with no fade band"
            " above it. The note that High contrast keeps its own yellow shows beside the accent."
        ),
        sources=SETTINGS,
        main=True,
    ),
    Screen(
        id="settings.look_cards",
        area="settings",
        prepare=_look_cards,
        checks=(
            "With Nocturne worn: its card has a 2 px ring in the look's accent on its top edge and a 24 px"
            " accent circle with a 16 px check, 10 px down and 12 px in from the top right (sampled on"
            " four sides of the check, not the picture's own accent). No other card has the ring, the"
            " badge or the word Current. Wearing a look moves nothing below the grid. Every More looks and"
            " Your looks picture is 160 px wide and drawn at that width (sharp, not stretched)."
        ),
        sources=SETTINGS + ("desktop/native/look_preview.py",),
        main=True,
    ),
    Screen(
        id="settings.look_card_focus",
        area="settings",
        prepare=_look_card_focus,
        checks=(
            "A card reached by Tab has a 2 px focus ring with a 2 px gap outside its face, reading at least"
            " 3 to 1 on the background behind it. A card clicked with the mouse shows no ring."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.look_pictures",
        area="settings",
        prepare=_look_pictures,
        checks=(
            "Each look's picture is drawn in that look's own page colour: Nocturne #0a0e27, Terminal"
            " #0d1117, High contrast #000000, and Paper, Poster, Terminal and Pastel are four different"
            " colours. A saved look 'Night study' with page #262d3b is drawn in #262d3b."
        ),
        sources=("desktop/native/look_preview.py", "desktop/native/look.py"),
    ),
    Screen(
        id="settings.light_dark_system",
        area="settings",
        prepare=_light_dark_system,
        checks=(
            "With System chosen: its segment shows the accent edge on top and Light and Dark do not, as a"
            " worn card does. The line 'Wearing System' sits below the segments. Choosing System moves"
            " nothing below the control."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.design_cards",
        area="settings",
        prepare=_design_cards,
        checks=(
            "The design cards fill their rows: the last card ends within 16 px of the grid's right edge, no"
            " card stands alone on a row, and the cards in a row are the same height. At 1280 wide the"
            " Main view cards sit in rows with more than one card."
        ),
        sources=SETTINGS + ("desktop/native/layouts/dialog.py",),
    ),
    Screen(
        id="settings.high_contrast_cards_at_large_text",
        area="settings",
        prepare=_high_contrast_cards_at_large_text,
        checks=(
            "At 1280 wide the look cards sit two to a row. At Large text the cards are wider than at normal"
            " text, and the name 'High contrast' is on one line: its text width fits the label's width and"
            " its height is one line plus 2 px."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.sidebar",
        area="settings",
        prepare=_sidebar,
        checks=(
            "Every section in the list has an icon, and only the chosen section has the accent bar at"
            " its left edge."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.accent_swatches",
        area="settings",
        prepare=_swatches,
        checks=(
            "The accent is five swatches in the look's own colours; Sea is chosen and its ring is the"
            " look's Sea colour for the light or dark axis in use."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.look_editor_open",
        area="settings",
        prepare=_look_editor_open,
        checks=(
            "Edit look opens the look editor over the whole Settings page (same rectangle), and"
            " Settings' own section list is put away under it. The Your own look row sits below the Look"
            " row on the page behind."
        ),
        sources=SETTINGS + ("desktop/native/look_editor.py",),
    ),
    Screen(
        id="settings.tab_to_the_last_switch",
        area="settings",
        prepare=_last_switch_focused,
        checks=(
            "With the last switch on Appearance focused after scrolling to the top, the page has scrolled"
            " so the switch ends above the footer's top edge, not under it. The page runs under the footer"
            " (it scrolls)."
        ),
        sources=SETTINGS,
    ),
    Screen(
        id="settings.retro_light",
        area="settings",
        prepare=lambda window: _retro(window, dark=False),
        checks=(
            "Under the Retro design the Settings page takes Retro's face colour for its ground whatever"
            " look is worn (the pixel at the right edge, middle height, is Retro's face). The Edit look"
            " button and Done each read at least 4.5 to 1: Retro's ink on Retro's face for the outlined"
            " one, Done's own filled pair for Done."
        ),
        sources=SETTINGS + ("desktop/native/layouts/retro.py",),
    ),
    Screen(
        id="settings.retro_dark",
        area="settings",
        prepare=lambda window: _retro(window, dark=True),
        checks=(
            "Retro plus the Dark look: the Text heading and the Text size line are drawn in Retro's ink,"
            " and the colour most of their pixels are painted in reads at least 4.5 to 1 on the card"
            " behind them (the worn Dark look's heading colours must not leak in). The outlined Edit look"
            " button and Done read at least 4.5 to 1, neither black on a dark face nor on the accent fill."
            " Under High contrast the heading still reads at 4.5 to 1."
        ),
        sources=SETTINGS + ("desktop/native/layouts/retro.py",),
    ),
    Screen(
        id="settings.canvas_follows_the_look",
        area="settings",
        prepare=_canvas_follows_look,
        checks=(
            "Choosing High contrast for the Bento design colours the visible Bento canvas at once, with the"
            " corner pixel #000000 and no frame of the old Indigo look left behind, before Settings is"
            " closed."
        ),
        sources=SETTINGS + ("desktop/native/layouts/",),
    ),
    Screen(
        id="settings.material_planning_cutoff",
        area="settings",
        prepare=_material_cutoff,
        checks=(
            "Material 3 Settings, Planning, in a window 800 px wide (also 860 and 900): the cut-off"
            " segmented control ends inside the page's clipping area (its right edge is no more than half"
            " a pixel past it), so no choice is cut off."
        ),
        sources=("desktop/native/material/",),
    ),
    Screen(
        id="settings.availability_cutoff",
        area="settings",
        prepare=_availability_cutoff,
        checks=(
            "On the Study hours sheet's cut-off tab the label 'No homework after' sits above the cut-off"
            " box and is shown once."
        ),
        sources=("desktop/native/widgets.py",),
    ),
]
