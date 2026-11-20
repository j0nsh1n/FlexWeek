# ruff: noqa: F811
"""Material is drawn in its own Qt Quick window, and the controller (NativeWindow) answers for it: a close
saves and quits once, or hides to the tray; Ctrl+S saves; the draw-error page is a window of its own and
Material's window is hidden while it shows."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from desktop.native import cpu_drawing  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_window import (  # noqa: E402, F401
    material_window,
    qapp,
)
from desktop.tests.material_support import (  # noqa: E402
    material_showing,
    page_showing,
    page_widget,
    pump,
    quick_of,
)
from desktop.tests.waiting import wait_until  # noqa: E402


class StubTray:
    """A tray that is up: what the window asks of it when it hides instead of closing."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def isVisible(self) -> bool:  # noqa: N802
        return True

    def supportsMessages(self) -> bool:  # noqa: N802
        return True

    def showMessage(self, title: str, *_rest: object) -> None:  # noqa: N802
        self.messages.append(title)

    def hide(self) -> None:
        pass


def _unsaved_change(window: NativeWindow) -> None:
    window.session.add_homework(
        {"id": "extra", "title": "Read chapter 4", "due": "2026-11-22", "estimate_min": 30, "revision": 0}
    )
    assert window.session.dirty


def _counting_quit(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Each real quit, as whether anything was still unsaved when it came. Nothing is really quit."""
    quits: list[bool] = []
    monkeypatch.setattr(window, "_quit_now", lambda: quits.append(window.session.dirty))
    return quits


def test_material_is_a_qt_quick_window_and_not_a_widget(
    qapp: QApplication, material_window: NativeWindow
) -> None:
    window = material_window
    page = quick_of(window)
    assert isinstance(page, QQuickView)
    assert not isinstance(page, QWidget)
    assert page.isTopLevel()
    assert window.windowHandle() is page
    assert not isinstance(window, QWidget)
    assert material_showing(window)
    assert window.isVisible() and page.isVisible()
    assert (page.width(), page.height()) == (1280, 800)


def test_closing_with_the_tray_off_saves_first_and_quits_once(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = material_window
    window._tray_icon = None
    quits = _counting_quit(window, monkeypatch)
    _unsaved_change(window)

    window.close()
    assert quits == [], "it must wait for the save, not quit on the unsaved week"
    wait_until(qapp, lambda: quits != [], what="the window to quit after saving")
    pump(qapp)
    window.close()
    pump(qapp)

    assert quits == [False], "one quit, with nothing left unsaved"


def test_the_close_button_event_takes_the_same_way_out(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The X button reaches the controller as a close event on Material's window."""
    window = material_window
    window._tray_icon = None
    quits = _counting_quit(window, monkeypatch)
    event = QCloseEvent()

    QApplication.sendEvent(quick_of(window), event)
    pump(qapp)
    QApplication.sendEvent(quick_of(window), QCloseEvent())
    pump(qapp)

    assert event.isAccepted()
    assert quits == [False]


def test_closing_with_the_tray_on_only_hides_the_window(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = material_window
    tray = StubTray()
    window._tray_icon = tray  # type: ignore[assignment]
    quits = _counting_quit(window, monkeypatch)
    assert window.isVisible()

    assert window.close() is False
    assert not window.isVisible() and not quick_of(window).isVisible()
    assert quits == []
    assert tray.messages == ["FlexWeek is still running"]

    # Shown again from the tray, then closed by the button's own event: hidden again, still no quit, and
    # the hint is not repeated.
    window.restore_window()
    assert window.isVisible()
    event = QCloseEvent()
    QApplication.sendEvent(quick_of(window), event)
    pump(qapp)
    assert not event.isAccepted()
    assert not window.isVisible()
    assert quits == []
    assert tray.messages == ["FlexWeek is still running"]


def test_closing_with_the_tray_setting_off_quits_even_when_the_tray_is_up(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = material_window
    window._tray_icon = StubTray()  # type: ignore[assignment]
    window.session.preferences = {**(window.session.preferences or {}), "tray_notifications": False}
    quits = _counting_quit(window, monkeypatch)

    window.close()
    pump(qapp)

    assert quits == [False]


def test_ctrl_s_saves_and_nothing_else_does(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = material_window
    saves: list[bool] = []
    monkeypatch.setattr(window.session, "save", lambda: saves.append(True))
    view = quick_of(window)

    QTest.keyClick(view, Qt.Key.Key_S)
    QTest.keyClick(view, Qt.Key.Key_S, Qt.KeyboardModifier.ShiftModifier)
    pump(qapp)
    assert saves == [], "S alone is not a save"

    QTest.keyClick(view, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    assert saves == [True]

    # A modal dialog open, or nobody signed in: the key is left alone.
    window.session.account, account = None, window.session.account
    QTest.keyClick(view, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    pump(qapp)
    window.session.account = account
    assert saves == [True]


def test_the_draw_error_page_is_a_window_of_its_own_and_hides_material(
    qapp: QApplication, material_window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(cpu_drawing.BACKEND_ENV, cpu_drawing.SOFTWARE)
    window = material_window
    view = quick_of(window)
    assert view.isVisible() and page_showing(window) == "materialPage"
    quits = _counting_quit(window, monkeypatch)

    window._give_up_material()
    pump(qapp)

    error = page_widget(window)
    assert page_showing(window) == "drawErrorPage"
    assert isinstance(error, QWidget) and error.isWindow() and error.parent() is None
    assert error.isVisible()
    assert not view.isVisible(), "Material's window is hidden while the error page shows"
    assert window.isVisible()
    for name, kind in (
        ("drawErrorLine", QLabel),
        ("drawErrorVersion", QLabel),
        ("drawErrorUpdateLine", QLabel),
        ("drawErrorQuit", QPushButton),
        ("drawErrorRetry", QPushButton),
        ("drawErrorInstall", QPushButton),
    ):
        assert error.findChild(kind, name) is not None, name
    assert error.findChild(QLabel, "drawErrorLine").text() == cpu_drawing.DRAW_ERROR

    # Closing the error window leaves the app, as the close button always did.
    QApplication.sendEvent(error, QCloseEvent())
    pump(qapp)
    assert quits == [False]
