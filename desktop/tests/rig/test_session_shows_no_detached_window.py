"""A student session must not show widgets that became windows only while being replaced."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import sunday_due
from desktop.native.look import VIEW_BUTTONS
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.rig.support_top_level_guard import (
    TopLevelShowGuard,
    prove_the_guard_sees_a_window,
    show_view,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-detached-window-test"])


def test_a_session_never_shows_a_detached_child_as_a_window(
    qapp: QApplication, window: NativeWindow, clock: FakeClock  # noqa: F811
) -> None:
    guard = TopLevelShowGuard(window)
    qapp.installEventFilter(guard)
    try:
        prove_the_guard_sees_a_window(qapp, guard)
        session = window.session
        wednesday = datetime.fromisoformat(session.week_start) + timedelta(days=2, hours=14)
        clock.set(wednesday)
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
            show_view(qapp, window, view)
        my_day = window.findChild(QAbstractButton, VIEW_BUTTONS[-1])
        assert my_day is not None, f"My day view control {VIEW_BUTTONS[-1]} is not available"
        my_day.click()
        settled(qapp, window)
        show_view(qapp, window, "week")
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
