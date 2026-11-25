# ruff: noqa: F811
"""The Material Day screen on the account's own data: the count line and the free-time card, the
clock setting, the free-time nudge preference, picking a date, and the controls a student reaches.

Expected strings come from the spec (Jonathan's words) and from the clock set in the fixture (Thursday
17:00: School 08:00-14:30 is over, the History essay waits at 18:45), not from reading the code's output.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import (  # noqa: E402
    bridge_of,
    pref,
    root_bridge,
    rows_of,
    seed_thursday,
)
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, quick_of, show_material, visuals  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> NativeWindow:
    return seed_thursday(qapp, open_light((1280, 800)), hour=17)


def test_the_day_screen_reads_the_real_day(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    prefs = dict(session.preferences or {})
    prefs["clock_24h"] = True
    prefs.pop("free_time_nudges", None)
    prefs.pop("nudges", None)
    session.preferences = prefs
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    assert day.property("leftLine") == "1 thing left today"
    assert day.property("showNow") is True
    assert day.property("nowTitle") == "Free for 1 h 45 min"
    assert day.property("nowMinutes") == 105
    assert day.property("nowLine") == "Next: History essay at 18:45"
    up = rows_of(day.property("upNext"))
    done = rows_of(day.property("doneRows"))
    assert [row["title"] for row in up] == ["History essay"]
    assert up[0]["subtitle"].startswith("18:45–19:45")
    assert up[0]["canFinish"] is True
    assert [row["title"] for row in done] == ["School"]
    assert done[0]["subtitle"] == "08:00–14:30"


def test_start_focus_on_the_day_screen_opens_the_next_homework(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    try:
        day.startFocus()
        pump(qapp)
        focus = window._material_page.bridge.focus
        assert str(focus.property("title")) == "History essay"
        assert str(day.property("nowTitle")) == "Free for 1 h 45 min"
    finally:
        window.session.reset_focus()
        # The Focus screen this opened would otherwise stay up.
        window._material_page.bridge.focus.hide()
        pump(qapp)


def test_the_clock_setting_changes_the_row_times(qapp: QApplication, window: NativeWindow) -> None:
    pref(window, clock_24h=False)
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    done = rows_of(day.property("doneRows"))
    assert done[0]["subtitle"] == "8 AM–2:30 PM"


def test_nudges_off_hides_the_free_time_card_on_day(qapp: QApplication, window: NativeWindow) -> None:
    pref(window, free_time_nudges=False)
    root = show_material(qapp, window)
    assert root_bridge(root).property("day").property("showNow") is False
    pref(window, free_time_nudges=True)
    root = show_material(qapp, window)
    assert root_bridge(root).property("day").property("showNow") is True


def test_picking_a_date_shows_that_day(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    root = show_material(qapp, window)
    day = root_bridge(root).property("day")
    thursday = date.fromisoformat(session.selected_day)
    friday = thursday + timedelta(days=1)
    assert day.property("miniDay") == thursday.day
    day.pickDay(friday.day)
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == friday.isoformat()
    assert day.property("miniDay") == friday.day
    assert day.property("leftLine") == "1 thing left"
    assert [row["title"] for row in rows_of(day.property("upNext"))] == ["School"]
    assert day.property("showNow") is False
    day.previousDay()
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == thursday.isoformat()
    assert day.property("leftLine") == "1 thing left today"
    day.nextDay()
    settled(qapp, window)
    pump(qapp)
    assert session.selected_day == friday.isoformat()
    day.pickDay(thursday.day)
    settled(qapp, window)
    assert session.selected_day == thursday.isoformat()


def test_the_day_screen_has_the_named_controls(qapp: QApplication, window: NativeWindow) -> None:
    root = show_material(qapp, window)
    bridge_of(window).showPage("day")
    pump(qapp)
    names = {str(item.objectName()) for item in visuals(root)}
    for name in (
        "materialDay",
        "dayPrevious",
        "dayNext",
        "dayLeftLine",
        "dayNow",
        "dayNowTitle",
        "dayStartFocus",
        "dayMonthToggle",
        "dayMonthSide",
        "dayMiniMonth",
        "dayNowLabel",
        "dayScroller",
        "dayHoursCard",
        "daySideDivider",
        "dayRightPanel",
    ):
        assert name in names, name


def test_dragging_the_day_divider_resizes_the_right_panel_and_remembers_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    bridge = bridge_of(window)
    bridge.showPage("day")
    pump(qapp)

    by_name = {str(item.objectName()): item for item in visuals(root) if item.objectName()}
    panel = by_name["dayRightPanel"]
    divider = by_name["daySideDivider"]
    start_width = int(round(panel.width()))
    assert start_width == 312

    quick = quick_of(window)
    assert quick is not None
    centre = divider.mapToScene(QPointF(divider.width() / 2, divider.height() / 2))
    start_pt = centre.toPoint()
    # Dragging the divider left widens the right panel by 72 px.
    end_pt = (centre - QPointF(72, 0)).toPoint()
    QTest.mousePress(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_pt)
    pump(qapp)
    QTest.mouseMove(quick, end_pt)
    pump(qapp)
    QTest.mouseRelease(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_pt)
    pump(qapp)

    resized = int(round(panel.width()))
    assert resized == start_width + 72
    assert int(bridge.property("daySideWidth")) == resized

    # Saving another look choice keeps the remembered divider width, and a fresh read restores it.
    bridge.settingsBridge.setDensity("compact")
    pump(qapp)
    bridge.set_appearance("light", "std")
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == resized
    assert int(round(panel.width())) == resized

    # Out-of-bounds values clamp to the sensible min/max range.
    bridge.setDaySideWidth(80)
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 240
    bridge.setDaySideWidth(900)
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 480

    # Clicking the divider without moving must not overwrite a wider saved width when the window caps it.
    window.resize(800, 800)
    pump(qapp, 10)
    capped_centre = divider.mapToScene(QPointF(divider.width() / 2, divider.height() / 2)).toPoint()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, capped_centre)
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 480
    window.resize(1280, 800)
    pump(qapp, 10)

    # Keyboard arrows resize the sidebar through the same clamp and persistence path.
    bridge.setDaySideWidth(312)
    pump(qapp)
    assert divider.property("activeFocusOnTab") is True
    divider.forceActiveFocus()
    pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_Left)
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 328
    QTest.keyClick(quick, Qt.Key.Key_Right)
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 312

    # Assistive technology reads the current width and can adjust it, like SliderRow.
    from PySide6.QtGui import QAccessible

    iface = QAccessible.queryAccessibleInterface(divider)
    assert iface is not None
    assert iface.role() == QAccessible.Role.Slider
    assert iface.text(QAccessible.Text.Name) == "Resize day sidebar"
    assert "312" in iface.text(QAccessible.Text.Description)
    actions = iface.actionInterface()
    assert actions is not None
    names = list(actions.actionNames())
    assert "Increase" in names
    assert "Decrease" in names
    # Screen readers invoke the advertised action by name; the convenience
    # increaseAction() slot does not reach QML handlers, so call doAction.
    actions.doAction("Increase")
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 328
    assert "328" in iface.text(QAccessible.Text.Description)
    actions.doAction("Decrease")
    pump(qapp)
    assert int(bridge.property("daySideWidth")) == 312

    bridge.settingsBridge.setDensity("comfortable")
    pump(qapp)


def test_the_side_panel_scrolls_a_focused_control_into_view(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A1: in a short window the month sits below the fold; focusing it scrolls the
    side panel so the focused control is on screen, as PairingDialog.ensureVisible does."""
    root = show_material(qapp, window)
    bridge = bridge_of(window)
    bridge.showPage("day")
    pump(qapp)
    by_name = {str(item.objectName()): item for item in visuals(root) if item.objectName()}
    panel = by_name["dayRightPanel"]
    month = by_name["dayMiniMonth"]
    window.resize(1280, 480)
    pump(qapp, 10)
    assert float(panel.property("contentHeight")) > float(panel.property("height"))
    month.forceActiveFocus()
    pump(qapp)
    assert month.property("activeFocus") is True
    m_top = month.mapToScene(QPointF(0, 0)).y()
    m_bottom = month.mapToScene(QPointF(0, month.height())).y()
    v_top = panel.mapToScene(QPointF(0, 0)).y()
    v_bottom = panel.mapToScene(QPointF(0, panel.height())).y()
    assert m_top >= v_top - 1, (m_top, v_top)
    assert m_bottom <= v_bottom + 1, (m_bottom, v_bottom)
    window.resize(1280, 800)
    pump(qapp, 10)


def test_mini_month_edge_columns_stay_clickable_at_smallest_sidebar_width_and_larger_text(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Finding 2: at 240 px sidebar width and Larger text (1.6x), both outer columns stay inside the pane."""
    root = show_material(qapp, window)
    bridge = bridge_of(window)
    bridge.showPage("day")
    bridge.settingsBridge.setTextSize("larger")
    bridge.setDaySideWidth(240)
    pump(qapp, 15)

    by_name = {str(item.objectName()): item for item in visuals(root) if item.objectName()}
    panel = by_name["dayRightPanel"]
    mini = by_name["dayMiniMonth"]
    panel_left = panel.mapToScene(QPointF(0, 0)).x()
    panel_right = panel.mapToScene(QPointF(panel.width(), 0)).x()
    mini_left = mini.mapToScene(QPointF(0, 0)).x()
    mini_right = mini.mapToScene(QPointF(mini.width(), 0)).x()
    assert mini_left >= panel_left
    assert mini_right <= panel_right

    # Pick an inside cell on column 0 (index 7 or 14) and column 6 (index 13 or 20) and click both.
    quick = quick_of(window)
    assert quick is not None
    mini_items = {str(item.objectName()): item for item in visuals(mini) if item.objectName()}
    for col_index in (14, 20):
        cell_text = mini_items[f"cell{col_index}"]
        wanted_day = int(str(cell_text.property("text")))
        spot = cell_text.mapToScene(QPointF(cell_text.width() / 2, cell_text.height() / 2))
        assert panel_left <= spot.x() <= panel_right
        QTest.mouseClick(quick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot.toPoint())
        settled(qapp, window)
        pump(qapp)
        assert int(bridge.property("day").property("miniDay")) == wanted_day

    bridge.settingsBridge.setTextSize("normal")
    bridge.setDaySideWidth(312)
    pump(qapp)


def _contrast(ink: str, paper: str) -> float:
    def lum(colour: str) -> float:
        text = colour.lstrip("#")[-6:]
        lin = []
        for i in (0, 2, 4):
            value = int(text[i : i + 2], 16) / 255
            lin.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    lighter, darker = sorted((lum(ink), lum(paper)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_the_now_label_reads_at_4_5_to_1_on_the_now_card(qapp: QApplication, window: NativeWindow) -> None:
    """The small bold "NOW" was drawn in primary on the primary container: 3.80:1 light, 3.98:1 dark.
    It is drawn in the card's own text colour, which reaches 4.5:1 in every look, light and dark,
    standard and high contrast."""
    from desktop.native.material.theme import CONTRASTS, MODES, ONE_MODE, PRESETS, scheme

    root = show_material(qapp, window)
    bridge_of(window).showPage("day")
    pump(qapp)
    by_name = {str(item.objectName()): item for item in visuals(root) if item.objectName()}
    label, title, card = by_name["dayNowLabel"], by_name["dayNowTitle"], by_name["dayNow"]
    assert label.property("color").name() == title.property("color").name()
    shown = _contrast(label.property("color").name(), card.property("color").name())
    assert shown >= 4.5, shown

    for preset in PRESETS:
        for mode in (ONE_MODE[preset],) if preset in ONE_MODE else MODES:
            for contrast in CONTRASTS:
                colours = scheme(preset, mode, contrast)
                ratio = _contrast(colours["onPrimaryContainer"], colours["primaryContainer"])
                assert ratio >= 4.5, (preset, mode, contrast, round(ratio, 2))
