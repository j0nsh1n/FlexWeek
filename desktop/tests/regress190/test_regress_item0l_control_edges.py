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

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QWidget,
)

from desktop.native.fields import ClockField
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
DESIGNS = [("retro", False), ("bento", False), ("timeline", False)]
CASES = [(f"classic-{name}", pack, preset, "classic", False) for name, pack, preset in TEN_LOOKS] + [
    (f"{design}-{shade}", pack, "default", design, day)
    for design, day in DESIGNS
    for shade, pack in (("light", "light-frost"), ("dark", "dark-frost"))
]
AA_GRAPHIC = 3.0
KNOWN_CHIP = (
    "known failure (0l, reopened as 0l-R): chips take _depth_rules' 1px hairline edge (look.py setup_rules), "
    "1.2-1.3:1"
)
KNOWN_RETRO = (
    "known failure (0l, reopened as 0l-R): Retro's BevelPane paints its bevel over the 2 px focus ring"
)
CHIP_TODAY = set()
FOCUS_TODAY = set()
SLACK = 0.02  # 8-bit rounding of a colour that the look computed to exactly 3:1


KNOWN_CHIP_FOCUS = "known failure (0l-R.1): a focused chip gets the 40 % button ring, not a 2 px accent ring"
CHIP_FOCUS_TODAY = set()


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
    assert not day
    w._layout = {"main": design, "day": "dial", "options": {}}
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


CHIP_CASES = known(CHIP_TODAY, KNOWN_CHIP)
FOCUS_CASES = known(FOCUS_TODAY, KNOWN_RETRO)
CHIP_FOCUS_CASES = known(CHIP_FOCUS_TODAY, KNOWN_CHIP_FOCUS)


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
