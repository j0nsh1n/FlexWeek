"""What the window's stylesheet says for a look: the faces, the padding and corners of cards and
controls, the ink of buttons, how depth is drawn, and the rules of the tray and the agenda rail.
These read the rules the app builds, as text; how they look is in the settings pictures."""

from __future__ import annotations

from desktop.native.calendar import CATEGORIES
from desktop.native.look import (
    FONT_FAMILIES,
    HEADING_NAMES,
    pack_stylesheet,
    resolved_palette,
)
from desktop.tests.settings.support_look import look_of


def faces(look: dict) -> tuple[str, str]:
    """The first face of the app-wide rule and of the headings' rule."""
    sheet = pack_stylesheet("slate", False, look)
    body = sheet.split("QWidget {")[1].split("font-family: ")[1].split(";")[0]
    headings = ", ".join(f"QLabel#{name}" for name in HEADING_NAMES) + " { font-family: "
    heading = sheet.split(headings)[1].split(";")[0]
    return body.split(", ")[0], heading.split(", ")[0]


def test_the_app_asks_for_its_own_inter_first_and_the_system_sans_after() -> None:
    assert FONT_FAMILIES["sans"].split(", ")[0] == "Inter"
    assert FONT_FAMILIES["sans"].endswith("sans-serif")
    assert "font-family: Inter, " in pack_stylesheet("slate", False, look_of("default"))


def test_serif_is_newsreader_headings_over_inter_and_mono_is_jetbrains_mono_throughout() -> None:
    """The Font knob (0.17): Sans is Inter; Serif keeps Inter for the words and sets headings in
    Newsreader; Mono is JetBrains Mono for both. Paper uses serif words and figures;
    Ink keeps serif headings. Terminal uses mono."""
    assert {"weekTitle", "settingsTitle", "authHeading"} <= set(HEADING_NAMES)
    for look, wanted in (
        (look_of("default"), ("Inter", "Inter")),
        (look_of("default", font="serif"), ("Inter", "Newsreader")),
        (look_of("default", font="mono"), ("JetBrains Mono", "JetBrains Mono")),
        (look_of("paper"), ("Newsreader", "Newsreader")),
        (look_of("ink"), ("Inter", "Newsreader")),
        (look_of("terminal"), ("JetBrains Mono", "JetBrains Mono")),
    ):
        assert faces(look) == wanted, look


def test_cards_are_padded_16_or_8_and_controls_keep_their_size() -> None:
    """Cards and dialogs padded 8 px read as cramped. The padding grew; a button, a field or a list
    kept its own, so none of them grew with it."""
    for density, card, control in (("comfortable", 16, 8), ("compact", 8, 4)):
        sheet = pack_stylesheet("slate", False, look_of("default", density=density))
        frames = sheet.split("QFrame, QGroupBox, QTableWidget, QListWidget {")[1].split("}")[0]
        assert f"padding: {card}px;" in frames, density
        assert f"QAbstractScrollArea {{ padding: {control}px; }}" in sheet, density
        button = sheet.split("QPushButton {")[1].split("}")[0]
        assert f"padding: {control}px {control * 2}px;" in button, density
        field = sheet.split("QLineEdit, QComboBox, QSpinBox, QTimeEdit, QDateTimeEdit {")[1].split("}")[0]
        assert f"padding: {control}px;" in field, density


def test_soft_corners_are_6_on_controls_and_10_on_cards() -> None:
    """Decision 5 of 0.17: Soft is the system's shape, 6 on controls and 10 on cards; Sharp is 0 and
    2 and Round 10 and 16, as the plan's knobs name them."""
    for corners, control, card in (("soft", 6, 10), ("sharp", 0, 2), ("rounded", 10, 16)):
        sheet = pack_stylesheet("light-frost", False, look_of("default", corners=corners))
        frames = sheet.split("QFrame, QGroupBox, QTableWidget, QListWidget {")[1].split("}")[0]
        button = sheet.split("QPushButton {")[1].split("}")[0]
        field = sheet.split("QLineEdit, QComboBox, QSpinBox, QTimeEdit, QDateTimeEdit {")[1].split("}")[0]
        toast = sheet.split("QFrame#toast {")[1].split("}")[0]
        sheet_radius = 16 if card else 0
        assert f"border-radius: {card}px;" in frames, corners
        assert f"border-radius: {sheet_radius}px;" in toast, "the toast is a sheet, at 16 (decision 20)"
        assert f"border-radius: {control}px;" in button and f"border-radius: {control}px;" in field, corners


def test_button_text_comes_from_the_palette_not_a_fixed_white() -> None:
    # White on Terminal's amber was 1.8 to 1. The ink has to be the one paired with the accent.
    sheet = pack_stylesheet("slate", False, look_of("terminal"))
    assert "QPushButton { background: #7fa8ff; color: #0b1224;" in sheet
    assert "#ffffff" not in sheet
    dark = pack_stylesheet("nocturne", True, look_of("default"), "gold")
    assert "QPushButton { background: #eab308; color: #0b1224;" in dark


def test_depth_is_drawn_with_edges_because_qt_has_no_shadows() -> None:
    soft = pack_stylesheet("nocturne", True, look_of("default"))
    flat = pack_stylesheet("nocturne", True, look_of("default", depth="none"))
    hard = pack_stylesheet("nocturne", True, look_of("default", depth="bold"))
    assert "border: 1px solid" in soft and "border: none;" not in soft.split("QHeaderView")[0]
    # An outlined button is its hairline (button_rules), so it keeps that edge in a flat look too.
    flat_rest = "}".join(
        rule for rule in flat.split("}") if 'outline="true"' not in rule and 'outlined="true"' not in rule
    )
    assert "QLineEdit, QComboBox, QSpinBox, QTimeEdit, QDateTimeEdit" in flat_rest
    assert "border: 1px solid" in flat_rest
    assert "border-bottom: 4px solid" in hard and "border-right: 4px solid" in hard


def test_a_tray_chip_is_edged_in_homeworks_colour_not_in_red() -> None:
    """Not placed yet is not a problem, so a tray chip's edge is homework's own mark in the look, not
    the red that said something was wrong (decision 8 of 0.17)."""
    homework = CATEGORIES["assignments"]
    high_contrast = {"preset": "high-contrast", "knobs": {}}
    for pack, dark, look, mark in (
        ("light-frost", False, None, homework["mark"]),
        ("dark-frost", True, None, homework["dark"][1]),
        ("system", False, high_contrast, homework["contrast"][1]),
    ):
        palette = resolved_palette(pack, dark, look)
        tray = pack_stylesheet(pack, dark, look).split('QPushButton[tray="true"] {')[1].split("}")[0]
        assert f"border-left: 4px solid {mark};" in tray, pack
        assert palette["error"] not in tray and "#ef4444" not in tray, pack


def test_the_agenda_rail_uses_type_and_space_not_pills() -> None:
    """Quiet split A: rail sections are ink and caption, not a count pill or nested cards."""
    cases = (
        ("light-frost", False, look_of("default")),
        ("dark-frost", True, look_of("default")),
        ("light-frost", False, look_of("high-contrast")),
    )
    for pack, dark, look in cases:
        palette = resolved_palette(pack, dark, look)
        sheet = pack_stylesheet(pack, dark, look)
        waiting = sheet.split("QLabel#railWaitingCount {")[1].split("}")[0]
        assert "background:" not in waiting, pack
        assert "border-radius" not in waiting, pack
        assert "padding:" not in waiting, pack
        assert f"color: {palette['muted']};" in waiting, pack
        labels = sheet.split('QLabel[railLabel="true"] {')[1].split("}")[0]
        assert f"color: {palette['text']};" in labels, pack
        assert f"color: {palette['muted']};" not in labels, pack
        bare = sheet.split("QFrame#rail,")[1].split("QListWidget#focusTasks")[0]
        assert "QWidget#railNextCard" in bare and "QWidget#railDue" in bare, pack
        assert "QLabel#railDueWhen" in sheet and "QLabel#railNextRowWhen" in sheet, pack
