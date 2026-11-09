"""The top bar's controls and the scroll bars every screen shares, by what they are and do: icons rather than
glyphs, the zoom pill, the key that rings a button and the click that does not, overlay scroll bars. How
they look (colours, order, hover and press, the raised view, bar widths) is pictures in
desktop/tests/pictures/_week_g14.py."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QWidget,
)

from desktop.native.widgets import keyboard_focus_rings
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import host  # noqa: F401

# The glyphs that stood in for icons before 0.17.
GLYPHS = "‹›⚙▾▸✕×✓⏱⋯＋−"

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 405,
    "days": [0, 1, 2, 3, 4],
}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-top-bar-controls"])


def show_view(qapp: QApplication, window: NativeWindow, view: str) -> None:
    """`view` of a week with school in it: an empty week shows its welcome instead of the hours."""
    session = window.session
    if not session.blocks:
        session.add_block(SCHOOL)
        session.save()
        wait_until(qapp, lambda: not session.busy and not session.dirty)
    window.findChild(QAbstractButton, f"view{view.title()}").click()
    wait_until(qapp, lambda: not session.busy)
    for _ in range(3):
        qapp.processEvents()


def bar(window: NativeWindow, name: str) -> QAbstractButton:
    found = window.findChild(QAbstractButton, name)
    assert found is not None, name
    return found


def test_no_glyph_stands_in_for_an_icon_in_the_chrome(qapp: QApplication, window: NativeWindow) -> None:
    """The gear was "⚙" in a fallback font, and the arrows, Add's arrow and the zoom were text too.
    Nothing on Week, Day or Month writes one; each icon button has an icon and words for a screen reader."""
    window.resize(1280, 800)
    for view in ("week", "day", "month"):
        show_view(qapp, window, view)
        page = window._stack.currentWidget()
        written = [
            (widget.objectName(), widget.text())
            for kind in (QAbstractButton, QLabel)
            for widget in page.findChildren(kind)
            if widget.isVisible() and any(glyph in widget.text() for glyph in GLYPHS)
        ]
        assert written == [], view
    for name in ("prevWeek", "nextWeek", "settingsGear", "addArrow", "weekZoomOut", "weekZoomIn"):
        button = bar(window, name)
        assert button.text() == "" and not button.icon().isNull(), name
        assert button.accessibleName() or button.toolTip(), f"{name} has no words for a screen reader"


def test_the_week_has_no_status_strip_under_the_bar(qapp: QApplication, window: NativeWindow) -> None:
    window.resize(1280, 800)
    show_view(qapp, window, "week")
    assert window.findChild(QWidget, "weekStatusStrip") is None
    assert window.findChild(QLabel, "weekStatusNext") is None
    assert window.findChild(QLabel, "weekStatusOverdue") is None


def test_the_zoom_is_one_pill_of_two_icon_buttons(qapp: QApplication, window: NativeWindow) -> None:
    window.resize(1280, 800)
    show_view(qapp, window, "week")
    out, into = bar(window, "weekZoomOut"), bar(window, "weekZoomIn")
    pill = out.parentWidget()
    assert pill is into.parentWidget() and pill.property("zoomPill")
    assert not out.icon().isNull() and not into.icon().isNull()


def test_the_bars_icons_are_drawn_again_in_the_new_words_colour_when_the_look_changes(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Each icon is drawn in its button's words colour, and drawn again when the look changes: a dark
    icon kept from Light on Dark's page could not be seen. The icon each button was last drawn with is
    recorded on it as its name and colours."""
    names = ("prevWeek", "nextWeek", "settingsGear", "addArrow")

    def dress(pack: str) -> dict[str, tuple[str, str, int]]:
        window.session.preferences = {**(window.session.preferences or {}), "theme_pack": pack}
        window._apply_appearance()
        for _ in range(3):
            qapp.processEvents()
        drawn = {}
        for name in names:
            button = bar(window, name)
            words = button.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText).name()
            drawn[name] = (str(button.property("iconTint")).split("|")[1], words, button.icon().cacheKey())
        return drawn

    light = dress("light-frost")
    dark = dress("dark-frost")
    for name in names:
        assert light[name][0] == light[name][1], (name, "light", light[name])
        assert dark[name][0] == dark[name][1], (name, "dark", dark[name])
        assert dark[name][1] != light[name][1], (name, "the look changed its words colour")
        assert dark[name][2] != light[name][2], (name, "its icon was drawn again")


def test_the_hours_month_and_settings_scroll_under_overlay_bars(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The bars lie over the content instead of taking a strip beside it: each is marked overlay, and the
    style then makes it transient."""

    def overlaid(area: QWidget) -> bool:
        scroll_bar = area.verticalScrollBar()
        transient = scroll_bar.style().styleHint(QStyle.StyleHint.SH_ScrollBar_Transient, None, scroll_bar)
        return bool(scroll_bar.property("overlay")) and bool(transient)

    show_view(qapp, window, "week")
    assert overlaid(window.week_table.scroll), "the hours"
    show_view(qapp, window, "month")
    wait_until(qapp, lambda: window.session.month_data is not None and window.month_grid.scroll.height() > 0)
    assert overlaid(window.month_grid.scroll), "Month"
    window._open_settings()
    wait_until(qapp, lambda: window._settings is not None and window._settings.isVisible())
    try:
        assert overlaid(window._settings.stack.currentWidget()), "Settings"
    finally:
        window._settings.close_page()


def keyed_row(qapp: QApplication, host: QWidget) -> tuple[QPushButton, QPushButton, QPushButton]:
    row = QHBoxLayout(host)
    made = []
    for words, kind in (("Add", None), ("Preview", "secondary"), ("More", "quiet")):
        button = QPushButton(words)
        if kind:
            button.setProperty(kind, True)
        row.addWidget(button)
        made.append(button)
    host.show()
    host.activateWindow()
    wait_until(qapp, host.isActiveWindow)
    return made[0], made[1], made[2]


def test_the_key_that_reaches_a_button_rings_it_and_a_click_does_not(
    qapp: QApplication, host: QWidget
) -> None:
    """Qt's focus also holds after a click, which would ring every button pressed, so only Tab marks a
    button as reached by the keyboard (its ring is drawn from that mark)."""
    keyboard_focus_rings(qapp)
    primary, _secondary, quiet = keyed_row(qapp, host)
    for button in (primary, quiet):
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert button.hasFocus() and not button.property("keyfocus"), f"{button.text()} ringed by a click"
        # Tab round to it again, as a student does.
        for _ in range(3):
            QTest.keyClick(host.focusWidget(), Qt.Key.Key_Tab)
        qapp.processEvents()
        assert button.hasFocus() and button.property("keyfocus"), button.text()
