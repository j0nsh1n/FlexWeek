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
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QHBoxLayout,
    QPushButton,
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
