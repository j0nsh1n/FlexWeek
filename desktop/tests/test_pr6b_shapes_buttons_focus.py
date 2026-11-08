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
    from PySide6.QtCore import QObject, QPointF, Qt
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
    assert 'text: root.focusTitle ? "Start " + root.focusTitle : "Start focus"' in now_card_text

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
    """A ring shows on the focused control only after a key; any mouse press hides it, the first click on
    a field included, and a key on the same control brings it back (Sol review of PR 6b)."""
    from desktop.native.material.focus_visible import install

    view, root = gallery
    assert install(view.engine()) is not None
    button = _find(root, "filledMeasure")
    ring = _child(button, "focusRing")
    field = _find(root, "fieldMeasure")
    dest = _find(root, "destMeasure")
    dest_ring = _child(dest, "focusRing")

    view.requestActivate()
    QTest.keyClick(view, Qt.Key_Tab)
    button.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()
    assert ring.property("shown") is True
    assert _border_width(ring) == 2
    assert ring.property("radius") == 10
    assert QColor(ring.property("ring")).name() == "#3d6fc4"
    assert ring.width() == button.width() + 8

    # A press anywhere hides the ring, even though the button keeps focus.
    _click(view, dest)
    assert button.hasActiveFocus()
    assert ring.property("shown") is False

    # A key on the same control brings it back.
    QTest.keyClick(view, Qt.Key_Shift)
    QGuiApplication.processEvents()
    assert ring.property("shown") is True

    # A click into a field focuses it; the field marks focus with its own border, not a ring.
    _click(view, field)
    assert field.property("activeFocus") or any(
        child.hasActiveFocus() for child in field.findChildren(type(field))
    )

    # Focus given from code after a click (a mouse-opened sheet's first field) stays quiet too.
    dest.forceActiveFocus(Qt.OtherFocusReason)
    QGuiApplication.processEvents()
    assert dest.hasActiveFocus()
    assert dest_ring.property("shown") is False
    QTest.keyClick(view, Qt.Key_Shift)
    QGuiApplication.processEvents()
    assert dest_ring.property("shown") is True
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
    """OutlinedField focused, Material 3 (Jonathan 2026-11-07): its own border turns the accent and
    2 px, and there is no outer ring."""
    _view, root = gallery
    field = _find(root, "fieldMeasure")
    shape = _child(field, "shape")
    input_item = _child(field, "fieldInput")

    assert _border_width(shape) == 1
    assert _border_color(shape).name() == "#64748b"
    assert not field.findChildren(QObject, "focusRing")

    input_item.forceActiveFocus(Qt.TabFocusReason)
    QGuiApplication.processEvents()

    assert _border_width(shape) == 2
    assert _border_color(shape).name() == "#3d6fc4"


def _prompt_button_lists() -> list[tuple[str, list[dict]]]:
    """Every `buttons: [...]` a settings Prompt is given, evaluated as the JavaScript it is."""
    from PySide6.QtQml import QJSEngine

    engine = QJSEngine()
    found: list[tuple[str, list[dict]]] = []
    for path in sorted(QML.rglob("*.qml")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\bbuttons:\s*\[", text):
            depth, end = 0, match.end() - 1
            for end in range(match.end() - 1, len(text)):
                depth += {"[": 1, "]": -1}.get(text[end], 0)
                if depth == 0:
                    break
            value = engine.evaluate("(" + text[match.end() - 1 : end + 1] + ")")
            assert not value.isError(), f"{path.name}: {value.toString()}"
            found.append((path.name, value.toVariant()))
    return found


def test_every_settings_prompt_has_at_most_one_filled_button(qapp: QGuiApplication) -> None:
    """Each prompt is its own screen: one filled button at most (Jonathan's rule, FIX-SPEC PR 6)."""
    lists = _prompt_button_lists()
    names = {name for name, _buttons in lists}
    assert {"AdvancedPage.qml", "SettingsView.qml"} <= names, names
    for name, buttons in lists:
        filled = [button["label"] for button in buttons if button.get("kind", "text") == "filled"]
        assert len(filled) <= 1, f"{name}: {filled}"
