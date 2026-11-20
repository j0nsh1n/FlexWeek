"""What the tests that were once one file, "Layouts in the real window", share: the signed-in week they
start from, and the small helpers they read the window with. The tests live by area (day, month, myday,
focus, sheets, settings, week, planner, updater, sync); the window comes from the light app."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, QStandardPaths, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QApplication,
    QDialog,
    QPushButton,
    QWidget,
)

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import LightWindows  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import PASSWORD, look_file, settled  # noqa: E402

SPOTIFY_TRACK = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-layouts-window-test"])


def add_school_week(qapp: QApplication, made: NativeWindow) -> None:
    """School every weekday morning and a History essay planned for Thursday 18:45, on the clock's
    Thursday 19:00 (backend.tests.fake_clock)."""
    session = made.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, made)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    settled(qapp, made)


def school_week(window: NativeWindow) -> None:
    """For a picture's `prepare`: the window the renderer opened gets the same week the tests start from."""
    add_school_week(QApplication.instance(), window)




@pytest.fixture()
def window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """A light window signed in on this week with School and a History essay planned for Thursday
    evening, the clock at Thursday 19:00."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open()
        add_school_week(qapp, made)
        yield made
    finally:
        windows.close()


def click(window: NativeWindow, name: str) -> None:
    window.findChild(QAbstractButton, name).click()






def _send(widget: QWidget, kind: QEvent.Type, at: QPoint, held: bool) -> None:
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind,
        QPointF(widget.mapFromGlobal(at)),
        QPointF(at),
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)






def press(dialog: QDialog, name: str) -> int:
    """What a student does in the homework editor: press one button, which closes it."""
    dialog.findChild(QPushButton, name).click()
    return QDialog.DialogCode.Accepted


def preference_puts(window: NativeWindow) -> list[dict]:
    """Every preferences save the session sends, with what it sent."""
    sent: list[dict] = []
    real = window.session.client.request

    def spy(method, path, payload, on_success, on_error):  # type: ignore[no-untyped-def]
        if method == "PUT" and path == "/api/preferences":
            sent.append(dict(payload))
        return real(method, path, payload, on_success, on_error)

    window.session.client.request = spy  # type: ignore[method-assign]
    return sent






# The More menu and the Add menu ---------------------------------------------------------------------








# Words on screen -------------------------------------------------------------------------------------




# Sounds and updates the window is given instead of the real ones ------------------------------------


class RingRecorder:
    """Stands in for the window's Bell so the ringing decision is visible without a sound card."""

    def __init__(self) -> None:
        self.started: list[tuple[str, object]] = []
        self.stops = 0
        self.ringing = False

    def start(self, tone: str, volume: object) -> bool:
        self.started.append((tone, volume))
        self.ringing = True
        return True

    def once(self, tone: str, volume: object) -> bool:
        self.started.append((tone, volume))
        return True

    def stop(self) -> None:
        self.stops += 1
        self.ringing = False


def no_spotify(monkeypatch: pytest.MonkeyPatch, opened: list) -> None:
    """Nothing in a test may hand a URL to the real desktop, which would open a browser."""
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        staticmethod(lambda url: bool(opened.append(url.toString())) or True),
    )


class FakeUpdater:
    """Stands in for the real one so no test reaches the network."""

    def __init__(self) -> None:
        self.checks = 0
        self.downloads: list[dict] = []
        self.busy = False

    def check(self, *, developer: bool = False) -> None:
        self.checks += 1
        self.developer = developer

    def download(self, update: dict) -> None:
        self.downloads.append(update)


# Homework editor steps ---------------------------------------------------------------------------------


def go_when(dialog) -> None:
    """Add homework's second question. The demo hides Due until What has a title."""
    if dialog._add_step is None or dialog._add_step >= 1:
        return
    if not dialog.title.text().strip():
        dialog.title.setText("History essay")
    dialog._save.click()
    QApplication.processEvents()


def go_length(dialog) -> None:
    """Add homework's third question. Estimated time is not on the first page."""
    go_when(dialog)
    if dialog._add_step is None or dialog._add_step >= 2:
        return
    dialog._save.click()
    QApplication.processEvents()


def monday_of_week(window: NativeWindow) -> datetime:
    return datetime.fromisoformat(window.session.week_start)


def thursday_at(window: NativeWindow, hours: int, minutes: int = 0) -> datetime:
    return monday_of_week(window) + timedelta(days=3, hours=hours, minutes=minutes)










__all__ = [
    "PASSWORD",
    "SPOTIFY_TRACK",
    "FakeUpdater",
    "RingRecorder",
    "add_school_week",
    "click",
    "go_length",
    "go_when",
    "look_file",
    "monday_of_week",
    "no_spotify",
    "preference_puts",
    "press",
    "qapp",
    "school_week",
    "settled",
    "thursday_at",
    "wait_until",
    "window",
]
