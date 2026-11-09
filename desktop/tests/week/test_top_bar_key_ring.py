"""The top bar's buttons show a focus ring when the keyboard reaches them, and only then: not after a click,
not on a plain button, and it leaves with the focus."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

from desktop.native.widgets import Segment, SegmentTrack, keyboard_focus_rings
from desktop.tests.window_support import host, qapp  # noqa: F401

BAR = (
    "prevWeek", "nextWeek", "todayWeek", "addButton", "addArrow", "solveButton", "moreButton", "settingsGear",
)


def make_bar(qapp: QApplication, host: QWidget) -> dict[str, QPushButton]:
    row = QHBoxLayout(host)
    row.setContentsMargins(24, 24, 24, 24)
    row.setSpacing(16)
    made: dict[str, QPushButton] = {}
    for name in BAR:
        button = QPushButton("" if name in ("prevWeek", "nextWeek", "settingsGear", "addArrow") else name)
        button.setObjectName(name)
        row.addWidget(button)
        made[name] = button
    track = SegmentTrack()
    track.setObjectName("segments")
    inside = QHBoxLayout(track)
    inside.setContentsMargins(0, 0, 0, 0)
    week = Segment("Week")
    week.setObjectName("viewWeek")
    week.setCheckable(True)
    track.add(week)
    row.addWidget(track)
    made["viewWeek"] = week
    made["cancel"] = QPushButton("Cancel")
    row.addWidget(made["cancel"])
    host.show()
    host.activateWindow()
    QTest.qWaitForWindowActive(host)
    for _ in range(3):
        qapp.processEvents()
    return made


def ring_of(host: QWidget) -> QWidget | None:
    return next((child for child in host.children() if child.objectName() == "barFocusRing"), None)


def tab_to(qapp: QApplication, button: QPushButton) -> None:
    # A window's first button already has the focus when it opens, and focusing it again says nothing.
    button.clearFocus()
    qapp.processEvents()
    button.setFocus(Qt.FocusReason.TabFocusReason)
    for _ in range(3):
        qapp.processEvents()


def test_a_bar_button_reached_by_key_is_ringed(qapp: QApplication, host: QWidget) -> None:
    keyboard_focus_rings(qapp)
    bar = make_bar(qapp, host)
    for name in (*BAR, "viewWeek"):
        button = bar[name]
        tab_to(qapp, button)
        ring = ring_of(host)
        assert ring is not None and ring.isVisible(), name
        middle = button.mapTo(host, QPoint(button.width() // 2, button.height() // 2))
        assert ring.geometry().contains(middle), f"{name}: the ring is not around the button"


def test_a_click_and_a_plain_button_show_no_ring_and_the_ring_goes_with_the_focus(
    qapp: QApplication, host: QWidget
) -> None:
    keyboard_focus_rings(qapp)
    bar = make_bar(qapp, host)
    QTest.mouseClick(bar["prevWeek"], Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert ring_of(host) is None or not ring_of(host).isVisible()
    tab_to(qapp, bar["cancel"])
    assert ring_of(host) is None or not ring_of(host).isVisible()
    tab_to(qapp, bar["nextWeek"])
    assert ring_of(host).isVisible()
    bar["cancel"].setFocus(Qt.FocusReason.TabFocusReason)
    qapp.processEvents()
    assert not ring_of(host).isVisible()
