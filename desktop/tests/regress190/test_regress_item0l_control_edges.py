"""Regression for fix-specs.md item 0l: control edges and the off switch track reach 3:1.

Measured from pixels, as drawn: each look is put on a signed-in window with the window's own
`_apply_appearance`, then the real Edit block sheet and Settings are opened and grabbed. For each
control the edge pixel is compared with the control's own fill and with the card right outside it
(the lower contrast counts), as the spec's guard says:

* fields (Title), dropdowns (Type of block) and time boxes (Start): resting edge >= 3:1;
* day chips (the pill buttons): resting edge >= 3:1;
* the focused field: a 2 px ring >= 3:1 against fill and card, and stronger than the resting edge;
* Settings' off switch: its track >= 3:1 against the card.

Looks: the ten looks on Today's app (classic), then Retro desktop, Clay deck, Bento, Mission control,
Timeline, and the Day dial and One thing day views, each in Light and in Dark. Every design ships on
"Match my look" (checked in 0.19.0's registry), and sheets and Settings wear the look in every design
(window.py `_apply_appearance`), so the design rows guard that dressing a design never changes the
controls. Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QSignalBlocker, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QWidget,
)

from desktop.native.fields import ClockField
from desktop.native.settings import SECTIONS
from desktop.native.widgets import BlockDialog
from desktop.tests.window_support import free, qapp, server, settled, signed_out, window  # noqa: F401

# (id, theme pack, look preset, main design, day design, day view?)
TEN_LOOKS = [
    ("light", "light-frost", "default"),
    ("dark", "dark-frost", "default"),
    ("high-contrast", "light-frost", "high-contrast"),
    ("nocturne", "nocturne", "default"),
    ("slate", "slate", "default"),
    ("poster", "light-frost", "poster"),
    ("terminal", "light-frost", "terminal"),
    ("paper", "light-frost", "paper"),
    ("ink", "light-frost", "ink"),
    ("pastel", "light-frost", "pastel"),
]
DESIGNS = [("retro", False), ("clay", False), ("bento", False), ("mission", False), ("timeline", False),
           ("dial", True), ("one", True)]
CASES = [(f"classic-{name}", pack, preset, "classic", False) for name, pack, preset in TEN_LOOKS] + [
    (f"{design}-{shade}", pack, "default", design, day)
    for design, day in DESIGNS
    for shade, pack in (("light", "light-frost"), ("dark", "dark-frost"))
]
AA_GRAPHIC = 3.0
KNOWN_KNOB = "known failure (0l-R): the off switch's knob is hard-coded #ffffff (widgets.py control_art)"
KNOWN_CHIP = (
    "known failure (0l, reopened as 0l-R): chips take _depth_rules' 1px hairline edge (look.py setup_rules), "
    "1.2-1.3:1"
)
KNOWN_RETRO = (
    "known failure (0l, reopened as 0l-R): Retro's BevelPane paints its bevel over the 2 px focus ring"
)
# Measured on 0.19.0 (0204dfe3) offscreen.
KNOB_TODAY = {
    "bento-dark",
    "classic-dark",
    "classic-high-contrast",
    "classic-ink",
    "classic-nocturne",
    "classic-terminal",
    "clay-dark",
    "dial-dark",
    "mission-dark",
    "one-dark",
    "retro-dark",
    "timeline-dark",
}
CHIP_TODAY = {
    "bento-dark",
    "bento-light",
    "classic-dark",
    "classic-ink",
    "classic-light",
    "classic-nocturne",
    "classic-pastel",
    "classic-slate",
    "classic-terminal",
    "clay-dark",
    "clay-light",
    "dial-dark",
    "dial-light",
    "mission-dark",
    "mission-light",
    "one-dark",
    "one-light",
    "retro-light",
    "timeline-dark",
    "timeline-light",
}
FOCUS_TODAY = {"retro-light", "retro-dark"}
SLACK = 0.02  # 8-bit rounding of a colour that the look computed to exactly 3:1


KNOWN_CHIP_FOCUS = "known failure (0l-R.1): a focused chip gets the 40 % button ring, not a 2 px accent ring"
KNOWN_DISABLED = "known failure (0l-R.2): a disabled switch's outline falls under 3:1 on its card"
CHIP_FOCUS_TODAY = {
    "bento-dark",
    "bento-light",
    "classic-dark",
    "classic-ink",
    "classic-light",
    "classic-nocturne",
    "classic-paper",
    "classic-pastel",
    "classic-poster",
    "classic-slate",
    "classic-terminal",
    "clay-dark",
    "clay-light",
    "dial-dark",
    "dial-light",
    "mission-dark",
    "mission-light",
    "one-dark",
    "one-light",
    "retro-dark",
    "retro-light",
    "timeline-dark",
    "timeline-light",
}
DISABLED_OFF_TODAY = {
    "bento-dark",
    "bento-light",
    "classic-dark",
    "classic-ink",
    "classic-light",
    "classic-nocturne",
    "classic-paper",
    "classic-pastel",
    "classic-slate",
    "classic-terminal",
    "clay-dark",
    "clay-light",
    "dial-dark",
    "dial-light",
    "mission-dark",
    "mission-light",
    "one-dark",
    "one-light",
    "retro-dark",
    "retro-light",
    "timeline-dark",
    "timeline-light",
}
DISABLED_ON_TODAY = {
    "bento-dark",
    "bento-light",
    "classic-dark",
    "classic-ink",
    "classic-light",
    "classic-nocturne",
    "classic-paper",
    "classic-pastel",
    "classic-slate",
    "classic-terminal",
    "clay-dark",
    "clay-light",
    "dial-dark",
    "dial-light",
    "mission-dark",
    "mission-light",
    "one-dark",
    "one-light",
    "retro-dark",
    "retro-light",
    "timeline-dark",
    "timeline-light",
}


def luminance(colour: QColor) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(colour.red()) + 0.7152 * channel(colour.green()) + 0.0722 * channel(colour.blue())


def contrast(a: QColor, b: QColor) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def dress(qapp, w, pack: str, preset: str, design: str, day: bool) -> None:
    w.resize(1280, 860)
    # Motion off: a grab during a sheet's fade-in or a page's slide read one flat colour everywhere.
    w.session.preferences = {**(w.session.preferences or {}), "theme_pack": pack, "motion": "off"}
    w._look = {"preset": preset, "knobs": {}}
    w.session.look = w._look
    if day:
        w._layout = {"main": "classic", "day": design, "options": {}}
        w._day_mode = True
    else:
        w._layout = {"main": design, "day": "one", "options": {}}
        w._day_mode = False
    w._apply_appearance()
    settled(qapp, w)


def pixel(image: QImage, at: QPoint) -> QColor:
    return QColor(image.pixel(at))


def top_edge(root: QWidget, image: QImage, widget: QWidget, ring: int = 1) -> dict:
    """Colours along the top edge, three quarters of the way across (clear of corners and words)."""
    rect = QRect(widget.mapTo(root, QPoint(0, 0)), widget.size())
    x = rect.left() + rect.width() * 3 // 4
    return {
        "card": pixel(image, QPoint(x, rect.top() - 2)),
        "edge": pixel(image, QPoint(x, rect.top())),
        "inner": pixel(image, QPoint(x, rect.top() + ring - 1)),
        "fill": pixel(image, QPoint(x, rect.top() + ring + 2)),
    }


def edge_problem(name: str, seen: dict) -> str | None:
    against_fill = contrast(seen["edge"], seen["fill"])
    against_card = contrast(seen["edge"], seen["card"])
    if min(against_fill, against_card) < AA_GRAPHIC - SLACK:
        return (f"{name}: edge {seen['edge'].name()} is {against_fill:.2f}:1 on its fill "
                f"{seen['fill'].name()} and {against_card:.2f}:1 on the card {seen['card'].name()}")
    return None


@pytest.fixture()
def block_sheet(qapp, window):
    sheets: list[BlockDialog] = []

    def open_sheet() -> BlockDialog:
        dialog = BlockDialog(window, day=2, start="16:00", duration_min=60)
        dialog.show()
        dialog.activateWindow()
        settled(qapp, window)
        QTest.qWait(150)
        sheets.append(dialog)
        return dialog

    yield open_sheet
    for dialog in sheets:
        dialog.hide()
        free(dialog)


def controls(dialog: BlockDialog) -> dict[str, QWidget]:
    pill = next(b for b in dialog.findChildren(QPushButton)
                if b.property("pill") and b.isVisible() and not b.isChecked())
    return {
        "field (Title)": dialog.findChild(QLineEdit, "blockTitle"),
        "dropdown (Type)": dialog.findChild(QComboBox, "blockCategory"),
        "time box (Start)": dialog.findChild(ClockField, "blockStart"),
        "day chip": pill,
    }


IDS = [case[0] for case in CASES]


def known(today: set[str], reason: str) -> list:
    return [
        pytest.param(*case, marks=pytest.mark.xfail(strict=True, reason=reason)) if case[0] in today else case
        for case in CASES
    ]


KNOB_CASES = known(KNOB_TODAY, KNOWN_KNOB)
CHIP_CASES = known(CHIP_TODAY, KNOWN_CHIP)
FOCUS_CASES = known(FOCUS_TODAY, KNOWN_RETRO)
CHIP_FOCUS_CASES = known(CHIP_FOCUS_TODAY, KNOWN_CHIP_FOCUS)
DISABLED_OFF_CASES = known(DISABLED_OFF_TODAY, KNOWN_DISABLED)
DISABLED_ON_CASES = known(DISABLED_ON_TODAY, KNOWN_DISABLED)


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), CASES, ids=IDS)
def test_0l_resting_edges_of_fields_dropdowns_time_boxes_reach_3_to_1(
    qapp, window, block_sheet, name, pack, preset, design, day
) -> None:
    dress(qapp, window, pack, preset, design, day)
    dialog = block_sheet()
    # Focus on a button in the sheet: every field's edge at rest.
    next(b for b in dialog.findChildren(QPushButton) if b.isVisible() and not b.property("pill")).setFocus()
    QApplication.processEvents()
    image = dialog.grab().toImage()
    found = controls(dialog)
    problems = [
        edge_problem(label, top_edge(dialog, image, widget))
        for label, widget in found.items() if label != "day chip"
    ]
    assert [p for p in problems if p] == []


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), CHIP_CASES, ids=IDS)
def test_0l_resting_edge_of_a_day_chip_reaches_3_to_1(
    qapp, window, block_sheet, name, pack, preset, design, day
) -> None:
    dress(qapp, window, pack, preset, design, day)
    dialog = block_sheet()
    image = dialog.grab().toImage()
    chip = controls(dialog)["day chip"]
    assert edge_problem(f"day chip {chip.text()!r}", top_edge(dialog, image, chip)) is None


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), FOCUS_CASES, ids=IDS)
def test_0l_a_focused_field_has_a_2px_ring_at_3_to_1_stronger_than_its_edge(
    qapp, window, block_sheet, name, pack, preset, design, day
) -> None:
    dress(qapp, window, pack, preset, design, day)
    dialog = block_sheet()
    title = dialog.findChild(QLineEdit, "blockTitle")
    other = dialog.findChild(ClockField, "blockStart")
    other.setFocus()
    QApplication.processEvents()
    resting = top_edge(dialog, dialog.grab().toImage(), title)
    title.setFocus()
    QApplication.processEvents()
    assert title.hasFocus()
    ring = top_edge(dialog, dialog.grab().toImage(), title, ring=2)
    two_px = f"ring is not 2 px: {ring['edge'].name()} then {ring['inner'].name()}"
    assert ring["inner"] == ring["edge"], two_px
    assert edge_problem("focused Title", ring) is None
    rest = min(contrast(resting["edge"], resting["fill"]), contrast(resting["edge"], resting["card"]))
    focus = min(contrast(ring["edge"], ring["fill"]), contrast(ring["edge"], ring["card"]))
    if preset != "high-contrast":  # the spec: High contrast is already fine
        assert focus > rest, f"focus ring {focus:.2f}:1 is not stronger than the resting edge {rest:.2f}:1"


def track_on_card(track: QColor, card: QColor, _knob: QColor) -> None:
    ratio = contrast(track, card)
    said = f"track {track.name()} is {ratio:.2f}:1 on the card {card.name()}"
    assert ratio >= AA_GRAPHIC - SLACK, said


def knob_on_track(track: QColor, _card: QColor, knob: QColor) -> None:
    ratio = contrast(knob, track)
    said = f"off knob {knob.name()} is {ratio:.2f}:1 on its track {track.name()}"
    assert ratio >= AA_GRAPHIC - SLACK, said


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), CASES, ids=IDS)
def test_0l_the_off_switch_track_reaches_3_to_1_on_its_card(
    qapp, window, name, pack, preset, design, day
) -> None:
    off_switch(qapp, window, pack, preset, design, day, track_on_card)




@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), KNOB_CASES, ids=IDS)
def test_0l_r_the_off_switch_knob_reaches_3_to_1_on_its_track(
    qapp, window, name, pack, preset, design, day
) -> None:
    """0l-R (QA, 0.19.0): the off knob is hard-coded white, unseen on the near-white track of dark looks."""
    off_switch(qapp, window, pack, preset, design, day, knob_on_track)


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), CHIP_FOCUS_CASES, ids=IDS)
def test_0l_a_focused_day_chip_has_a_2px_ring_at_3_to_1_stronger_than_its_edge(
    qapp, window, block_sheet, name, pack, preset, design, day
) -> None:
    """0l / 0l-R.1: chips get the 2 px accent focus ring, not the 40 % button ring. The chip is reached the
    keyboard way (TabFocusReason), so a ring that shows only for the keyboard shows."""
    dress(qapp, window, pack, preset, design, day)
    dialog = block_sheet()
    chip = controls(dialog)["day chip"]
    dialog.findChild(QLineEdit, "blockTitle").setFocus()
    QApplication.processEvents()
    resting = top_edge(dialog, dialog.grab().toImage(), chip)
    chip.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    assert chip.hasFocus()
    ring = top_edge(dialog, dialog.grab().toImage(), chip, ring=2)
    two_px = f"ring is not 2 px: {ring['edge'].name()} then {ring['inner'].name()}"
    assert ring["inner"] == ring["edge"], two_px
    assert edge_problem(f"focused chip {chip.text()!r}", ring) is None
    rest = min(contrast(resting["edge"], resting["fill"]), contrast(resting["edge"], resting["card"]))
    focus = min(contrast(ring["edge"], ring["fill"]), contrast(ring["edge"], ring["card"]))
    if preset != "high-contrast":
        assert focus > rest, f"focus ring {focus:.2f}:1 is not stronger than the resting edge {rest:.2f}:1"


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), DISABLED_OFF_CASES, ids=IDS)
def test_0l_r_a_disabled_off_switch_keeps_a_3_to_1_outline_on_its_card(
    qapp, window, name, pack, preset, design, day
) -> None:
    """0l-R.2: "disabled versions stay readable at 3:1 for the outline" (the track against the card)."""
    off_switch(qapp, window, pack, preset, design, day, track_on_card, enabled=False, on=False)


@pytest.mark.parametrize(("name", "pack", "preset", "design", "day"), DISABLED_ON_CASES, ids=IDS)
def test_0l_r_a_disabled_on_switch_keeps_a_3_to_1_outline_on_its_card(
    qapp, window, name, pack, preset, design, day
) -> None:
    off_switch(qapp, window, pack, preset, design, day, track_on_card, enabled=False, on=True)


def off_switch(
    qapp, window, pack, preset, design, day, check, *, enabled: bool = True, on: bool = False
) -> None:
    dress(qapp, window, pack, preset, design, day)
    window._open_settings()
    page = window._settings
    page.nav.setCurrentRow(SECTIONS.index("Look"))
    settled(qapp, window)
    QTest.qWait(150)
    switch = page.fine_tune
    blocker = QSignalBlocker(switch)  # a checked Fine-tune would open its panel and move the page
    switch.setChecked(on)
    switch.setEnabled(enabled)
    del blocker
    switch.update()
    scroll = switch.parentWidget()
    while scroll is not None and not isinstance(scroll, QScrollArea):
        scroll = scroll.parentWidget()
    if scroll is not None:  # below the fold of the Look section, and the footer sits over the bottom
        scroll.ensureWidgetVisible(switch, 40, 160)  # 160: clear of the "Changes are saved" footer
    QApplication.processEvents()
    assert switch.isVisible()
    option, _ = switch._toggle()
    box = switch.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, switch)
    origin = switch.mapTo(window, QPoint(0, 0))
    image = window.grab().toImage()
    middle = origin.y() + box.center().y()
    track = pixel(image, QPoint(origin.x() + box.left() + box.width() * 3 // 4, middle))
    card = pixel(image, QPoint(origin.x() + box.left() - 3, middle))
    knob = pixel(image, QPoint(origin.x() + box.left() + box.width() * 3 // 10, middle))
    try:
        check(track, card, knob)
    finally:
        switch.setEnabled(True)
        window._close_settings(save=False)
        settled(qapp, window)
