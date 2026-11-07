"""The mouse wheel scrolls the page it is over. It changes a number box, time box or dropdown only
once the student has clicked into it: scrolling Settings used to change every box the pointer
passed on the way down."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, QTime  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.native.settings import SettingsPage  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests import light_app, window_support  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402

# Fixtures are found by their name in the test module. The window installs the app-wide wheel filter,
# so the first two tests open one although they never use it.
qapp = window_support.qapp
host = window_support.host
window = light_app.window


def page(parent: QWidget) -> tuple[QScrollArea, QLineEdit, QSpinBox, QTimeEdit, QComboBox]:
    area = QScrollArea(parent)
    body = QWidget()
    column = QVBoxLayout(body)
    typing = QLineEdit()
    spin = QSpinBox()
    spin.setRange(0, 100)
    spin.setValue(50)
    clock = QTimeEdit(QTime(16, 0))
    menu = QComboBox()
    menu.addItems(["One", "Two", "Three", "Four"])
    menu.setCurrentIndex(1)
    for widget in (typing, spin, clock, menu):
        column.addWidget(widget)
    column.addSpacing(2000)
    area.setWidget(body)
    area.setWidgetResizable(True)
    area.resize(320, 300)
    parent.resize(340, 320)
    return area, typing, spin, clock, menu


def settled(app: QApplication, widget: QWidget) -> None:
    """Shown, active and placed. Right after a window is exposed the window manager may still be moving
    it, and a wheel event aimed through the window then lands beside the box it was meant for: alone in
    a fresh process this test rolled over nothing and the page stayed put."""
    top = widget.window()
    wait_until(app, top.isExposed, what="the window being exposed")
    top.activateWindow()
    seen: list[tuple] = []

    def still() -> bool:
        now = (top.frameGeometry().getRect(), top.isActiveWindow())
        steady = bool(seen) and seen[-1] == now and now[1]
        seen.append(now)
        return steady

    wait_until(app, still, what="the window to stop moving and become active")


def roll(area: QScrollArea, over: QWidget) -> None:
    """One notch down, from the system, as a real mouse sends it: through the window."""
    at = QPointF(over.mapTo(area.window(), QPoint(12, over.height() // 2)))
    QTest.wheelEvent(area.window().windowHandle(), at, QPoint(0, -120))
    QApplication.processEvents()


def test_the_wheel_over_a_box_the_student_is_not_in_scrolls_the_page(
    qapp: QApplication, window: NativeWindow, host: QWidget
) -> None:
    area, typing, spin, clock, menu = page(host)
    host.show()
    settled(qapp, area)
    bar = area.verticalScrollBar()
    for box, value in ((spin, spin.value), (clock, clock.time), (menu, menu.currentIndex)):
        typing.setFocus()
        bar.setValue(0)
        before = value()
        roll(area, box)
        assert value() == before, f"{type(box).__name__} changed under a passing wheel"
        assert bar.value() > 0, f"the page did not scroll over the {type(box).__name__}"
        assert not box.hasFocus(), "the wheel is not a click; it must not take the keyboard"


def test_the_wheel_still_changes_a_box_the_student_clicked_into(
    qapp: QApplication, window: NativeWindow, host: QWidget
) -> None:
    area, _typing, spin, _clock, _menu = page(host)
    host.show()
    settled(qapp, area)
    spin.setFocus()
    roll(area, spin)
    assert spin.value() == 49


def test_scrolling_down_settings_leaves_the_focus_minutes_alone(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._open_settings()
    dialog = window._settings
    assert isinstance(dialog, SettingsPage)
    dialog.nav.setCurrentRow(2)
    qapp.processEvents()
    dialog.nav.setFocus()
    before = dialog.work.value()
    at = QPointF(dialog.work.mapTo(window, QPoint(12, dialog.work.height() // 2)))
    QTest.wheelEvent(window.windowHandle(), at, QPoint(0, -120))
    qapp.processEvents()
    assert dialog.work.value() == before
    dialog.close_page()
