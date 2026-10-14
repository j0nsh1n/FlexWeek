"""A student session must not show widgets that became windows only while being replaced."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QMenu, QPushButton, QWidget

from desktop.native.calendar import sunday_due
from desktop.native.look import VIEW_BUTTONS
from desktop.native.window import NativeWindow
from desktop.tests.test_top_bar import shown
from desktop.tests.window_support import (
    PASSWORD,
    USERNAME,
    past_setup,
    qapp,  # noqa: F401
    server,  # noqa: F401
    settled,
    signed_out,  # noqa: F401
    wait_until,
)


class TopLevelShowGuard(QObject):
    """Record any shown window that is not an expected app surface."""

    def __init__(self, main: NativeWindow) -> None:
        super().__init__()
        self.main = main
        self.shown: list[str] = []
        self.offscreen: list[str] = []
        self.unexpected: list[str] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
            description = (
                f"{type(watched).__name__}#{watched.objectName()} "
                f"title={watched.windowTitle()!r} type={watched.windowType()}"
            )
            self.shown.append(description)
            if watched.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):
                # Design previews receive Show to render a picture, while Qt keeps them offscreen.
                self.offscreen.append(description)
                return False
            allowed_types = {
                Qt.WindowType.Dialog,
                Qt.WindowType.Popup,
                Qt.WindowType.ToolTip,
                Qt.WindowType.Sheet,
            }
            if (
                watched is not self.main
                and not isinstance(watched, (QDialog, QMenu))
                and watched.windowType() not in allowed_types
            ):
                self.unexpected.append(description)
        return False


def test_student_session_never_shows_a_detached_child_as_a_window(
    qapp: QApplication, signed_out: NativeWindow
) -> None:
    window = signed_out
    guard = TopLevelShowGuard(window)
    qapp.installEventFilter(guard)
    try:
        # The filter must see a window being shown. What the session itself shows depends on what
        # earlier tests in this process left cached (design pictures are drawn once), so it is proved
        # here with a dialog of its own, which is an allowed kind.
        probe = QDialog()
        probe.setObjectName("guardProbe")
        probe.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        probe.show()
        qapp.processEvents()
        probe.hide()
        probe.deleteLater()
        assert any("#guardProbe " in line for line in guard.shown), "the app-wide filter saw no Show"
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(qapp, window)
        settled(qapp, window)

        window.session.logout()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "authPage")
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "signIn").click()
        wait_until(qapp, lambda: window.session.account is not None)
        settled(qapp, window)

        session = window.session
        wednesday = datetime.fromisoformat(session.week_start) + timedelta(days=2, hours=14)
        session.now_ms = lambda: int(wednesday.timestamp() * 1000)
        session.add_homework(
            {
                "id": "session-essay",
                "title": "History essay",
                "due": sunday_due(session.week_start),
                "estimate_min": 60,
                "revision": 0,
            }
        )
        session.save()
        settled(qapp, window)
        for _ in range(2):
            window.solve_button.click()
            settled(qapp, window)

        for view in ("week", "month", "day"):
            shown(qapp, window, view)
        my_day = window.findChild(QAbstractButton, VIEW_BUTTONS[-1])
        assert my_day is not None, f"My day view control {VIEW_BUTTONS[-1]} is not available"
        my_day.click()
        settled(qapp, window)
        shown(qapp, window, "week")
        window.next_nav.click()
        settled(qapp, window)
        window.prev_nav.click()
        settled(qapp, window)

        session.add_homework(
            {
                "id": "older-essay",
                "title": "Earlier essay",
                "due": (datetime.fromisoformat(session.week_start) - timedelta(days=1)).date().isoformat(),
                "estimate_min": 30,
                "revision": 0,
            }
        )
        session.save()
        settled(qapp, window)
        window._show_unfinished()
        wait_until(qapp, window.unfinished_panel.isVisible)
        window.unfinished_panel.findChild(QPushButton, "unfinishedDismiss").click()
        wait_until(qapp, lambda: not window.unfinished_panel.isVisible())
        window._show_unfinished()
        wait_until(qapp, window.unfinished_panel.isVisible)
        window.unfinished_panel.findChild(QPushButton, "unfinishedDismiss").click()
        wait_until(qapp, lambda: not window.unfinished_panel.isVisible())

        window._open_settings()
        page = window._settings
        assert page is not None
        page._open_customise()
        editor = page.editor
        assert editor is not None and editor.accents is not None
        editor.accents.setCurrentIndex((editor.accents.currentIndex() + 1) % editor.accents.count())
        editor.done.click()
        wait_until(qapp, lambda: page.editor is None)

        main_layout = page.layout_sections[0].pick
        main_layout.setCurrentIndex(main_layout.findData("timeline"))
        window._close_settings()
        settled(qapp, window)
        window._open_settings()
        page = window._settings
        assert page is not None
        main_layout = page.layout_sections[0].pick
        main_layout.setCurrentIndex(main_layout.findData("classic"))
        window._close_settings()
        settled(qapp, window)

        assert guard.unexpected == [], "Unexpected top-level Show events:\n" + "\n".join(guard.unexpected)
    finally:
        qapp.removeEventFilter(guard)
        guard.main = None
        guard.deleteLater()
