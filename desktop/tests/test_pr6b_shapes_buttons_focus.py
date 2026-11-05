"""Tests for PR 6b: B3a3 shapes, one filled button, keyboard-only focus rings, and nav rail tint.

Written from the FIX-SPEC PR 6b brief, not from current QML output.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

from desktop.tests.test_material_components import _child, _color, _find

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QGuiApplication
    from PySide6.QtQml import QQmlProperty
    from PySide6.QtTest import QTest

pytest_plugins = ["desktop.tests.test_material_components"]

ROOT = Path(__file__).resolve().parents[2]
QML = ROOT / "desktop" / "native" / "material" / "qml"

_FILLED = re.compile(r'kind:\s*"filled"')
_OUTLINED = re.compile(r'kind\s*:\s*["\']outlined["\']')
_BUTTON_FILLED = re.compile(r"Button\s*\{[^{}]*kind:\s*\"filled\"", re.DOTALL)


def _border_width(item) -> float:
    return QQmlProperty(item, "border.width").read()


def _border_color(item) -> QColor:
    return QColor(QQmlProperty(item, "border.color").read())


def _click(view, item) -> None:
    view.requestActivate()
    QGuiApplication.processEvents()
    centre = item.mapToItem(view.contentItem(), QPointF(item.width() / 2, item.height() / 2))
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, centre.toPoint())
    QGuiApplication.processEvents()


def test_cards_and_sheets_are_8_and_buttons_and_fields_are_6(
    gallery: tuple,
) -> None:
    """Cards, sheets, and dialogs have radius 8; buttons and text fields have radius 6."""
    _view, root = gallery

    dialog = _find(root, "dialogMeasure")
    card = _child(dialog, "dialogCard")
    assert card.property("radius") == 8

    group = _find(root, "groupMeasure")
    assert _child(group, "shape").property("radius") == 8

    button = _find(root, "filledMeasure")
    assert _child(button, "shape").property("radius") == 6

    field = _find(root, "fieldMeasure")
    assert _child(field, "shape").property("radius") == 6

    sheet_text = (QML / "sheets" / "SheetFrame.qml").read_text(encoding="utf-8")
    assert re.search(r"id:\s*card[\s\S]*?radius:\s*8", sheet_text) is not None


def test_chips_and_step_crumbs_are_pills() -> None:
    """Chips and step crumbs are pills with radius = height / 2 and no crumb outline."""
    for rel in (
        "setup/ChipRow.qml",
        "setup/DayChips.qml",
        "sheets/BlockSheet.qml",
        "sheets/HomeworkSheet.qml",
    ):
        text = (QML / rel).read_text(encoding="utf-8")
        assert "radius: height / 2" in text, rel

    crumbs = (QML / "sheets" / "HomeworkSheet.qml").read_text(encoding="utf-8")
    assert "border.width: 0" in crumbs


def test_no_outlined_buttons_are_left() -> None:
    """No QML control sets kind to outlined; leftover uses became text."""
    found: list[str] = []
    for path in QML.rglob("*.qml"):
        if _OUTLINED.search(path.read_text(encoding="utf-8")):
            found.append(str(path.relative_to(ROOT)))
    assert found == []


def test_each_screen_has_at_most_one_filled_button() -> None:
    """Main Week has only Plan; Add homework one; Day only NowCard Start focus; Advanced one."""
    week_text = (QML / "views" / "WeekView.qml").read_text(encoding="utf-8")
    assert _FILLED.findall(week_text) == []

    drawer_text = (QML / "week" / "HomeworkDrawer.qml").read_text(encoding="utf-8")
    # Plan is filled while something waits and a text button when nothing does (PR 6c).
    assert len(re.findall(r'kind:[^\n]*"filled"', drawer_text)) == 1
    assert 'objectName: "planHomework"' in drawer_text

    hw_sheet_text = (QML / "sheets" / "HomeworkSheet.qml").read_text(encoding="utf-8")
    assert len(_BUTTON_FILLED.findall(hw_sheet_text)) == 1
    assert 'objectName: "homeworkNext"' in hw_sheet_text

    now_card_text = (QML / "day" / "NowCard.qml").read_text(encoding="utf-8")
    assert len(_BUTTON_FILLED.findall(now_card_text)) == 1
    assert 'text: "Start focus"' in now_card_text

    day_lists_text = (QML / "day" / "DayLists.qml").read_text(encoding="utf-8")
    assert _BUTTON_FILLED.findall(day_lists_text) == []

    adv_text = (QML / "settings" / "AdvancedPage.qml").read_text(encoding="utf-8")
    assert len(_BUTTON_FILLED.findall(adv_text)) == 1
    assert 'objectName: "advancedDone"' in adv_text
    assert re.search(r'objectName: "fixAll"[\s\S]*?kind: "tonal"', adv_text)

    focus_text = (QML / "focus" / "FocusScreen.qml").read_text(encoding="utf-8")
    # Start and Pause are both filled in source; only one is visible at a time.
    assert len(_BUTTON_FILLED.findall(focus_text)) == 2
    assert 'objectName: "focusStart"' in focus_text
    assert 'objectName: "focusPause"' in focus_text
    assert re.search(r'objectName: "focusSkip"[\s\S]*?kind: "text"', focus_text)
    assert re.search(r'objectName: "focusFinished"[\s\S]*?kind: "tonal"', focus_text)


def test_the_add_button_is_card_coloured_with_an_accent_icon(
    gallery: tuple,
) -> None:
    """The FAB is card-coloured with a 1px edge and an accent icon in light and dark."""
    _view, root = gallery
    fab = _find(root, "fabMeasure")
    shape = _child(fab, "shape")
    icon = _child(fab, "icon")

    root.setProperty("scheme", "light")
    QGuiApplication.processEvents()
    assert shape.property("radius") == 6
    assert _border_width(shape) == 1
    assert _color(fab, "shape").name() == "#ffffff"
    assert _border_color(shape).name() == "#e5e9f0"
    assert QColor(icon.property("color")).name() == "#3d6fc4"

    root.setProperty("scheme", "dark")
    QGuiApplication.processEvents()
    assert _color(fab, "shape").name() == "#14171c"
    assert _border_color(shape).name() == "#252a33"
    assert QColor(icon.property("color")).name() == "#7fa8ff"

    root.setProperty("scheme", "light")
    QGuiApplication.processEvents()


def test_a_mouse_click_shows_no_ring_and_tab_does(
    gallery: tuple,
) -> None:
    """Mouse focus hides the ring; Tab / keyboard focus shows a 2px focusRing with a 2px gap."""
    view, root = gallery
    button = _find(root, "filledMeasure")
    ring = _child(button, "focusRing")

    dest = _find(root, "destMeasure")
    dest_ring = _child(dest, "focusRing")

    _click(view, button)
    assert button.hasActiveFocus()
    assert ring.property("shown") is False

    dest.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()
    button.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()
    assert button.hasActiveFocus()
    assert ring.property("shown") is True
    assert _border_width(ring) == 2
    assert ring.property("radius") == 10
    assert QColor(ring.property("ring")).name() == "#3d6fc4"
    assert ring.width() == button.width() + 8

    _click(view, dest)
    assert dest.hasActiveFocus()
    assert dest_ring.property("shown") is False

    button.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()
    dest.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()
    assert dest.hasActiveFocus()
    assert dest_ring.property("shown") is True
    assert _border_width(dest_ring) == 2
    assert QColor(dest_ring.property("ring")).name() == "#3d6fc4"


def test_the_selected_nav_item_has_a_tint_and_no_outline(
    gallery: tuple,
) -> None:
    """The selected NavDestination has secondaryContainer tint, primary icon, and no outline."""
    _view, root = gallery
    dest = _find(root, "destMeasure")
    indicator = _find(dest, "indicator")
    fill = _child(dest, "indicatorShape")
    icon = _child(dest, "icon")
    ring = _child(dest, "focusRing")

    assert dest.property("selected") is True
    assert ring.property("shown") is False
    assert _border_width(fill) == 0
    assert QColor(fill.property("color")).name() == "#e6edf8"
    assert QColor(icon.property("color")).name() == "#3d6fc4"
    assert indicator.width() == 56
    assert indicator.height() == 32


def test_a_focused_field_draws_one_border(
    gallery: tuple,
) -> None:
    """OutlinedField focused: own border stays 1px palette.outline; only the outer ring shows."""
    _view, root = gallery
    field = _find(root, "fieldMeasure")
    shape = _child(field, "shape")
    input_item = _child(field, "fieldInput")
    ring = _child(field, "focusRing")

    assert _border_width(shape) == 1
    assert ring.property("shown") is False

    input_item.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()

    assert _border_width(shape) == 1
    assert _border_color(shape).name() == "#64748b"
    assert ring.property("shown") is True
    assert _border_width(ring) == 2
    assert QColor(ring.property("ring")).name() == "#3d6fc4"
