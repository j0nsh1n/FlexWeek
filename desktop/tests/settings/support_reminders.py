"""What the tests of reminders and a block's song share: a stand-in tray, bell and Spotify app, the
clock held on Thursday evening, and a block to be reminded of.

`serve` and `launch` stay for test_spotify_one_link.py, which still opens the app on a local server."""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from backend.tests.fake_clock import CLOCK, START
from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.logic_support import past_setup
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import settled

PASSWORD = "a-long-test-password"
TRACK = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
TRACK_ADDRESS = "spotify:track:4cOdK2wGLETKBW3PvgPWqT"
OTHER = "https://open.spotify.com/track/1301WleyT98MSxVHPZCA6M"
OTHER_ADDRESS = "spotify:track:1301WleyT98MSxVHPZCA6M"
REMINDER = "Guitar practice starts soon — 6:45 PM · Thu"
PRACTICE_NOTICE = ("Guitar practice starts soon", "6:45 PM · Thu")


class Tray:
    """The system tray, as far as the window uses it for a notification."""

    def __init__(self) -> None:
        self.shown: list[tuple[str, str]] = []

    def supportsMessages(self) -> bool:  # noqa: N802
        return True

    def showMessage(self, title: str, body: str, *_rest: object) -> None:  # noqa: N802
        self.shown.append((title, body))

    def isVisible(self) -> bool:  # noqa: N802
        return True

    def hide(self) -> None:
        return None


class Bell:
    """The window's tone: what rang once, and what rang until stopped."""

    def __init__(self) -> None:
        self.once_rung: list[str] = []
        self.started: list[str] = []
        self.ringing = False

    def once(self, tone: str, _volume: object) -> bool:
        self.once_rung.append(tone)
        return True

    def start(self, tone: str, _volume: object) -> bool:
        self.started.append(tone)
        self.ringing = True
        return True

    def stop(self) -> None:
        self.ringing = False


class SpotifyApp:
    """The student's Spotify app on the session bus: what it was asked to play, and each pause."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.paused = 0
        self.is_playing = False

    def reachable(self) -> bool:
        return True

    def running(self) -> bool:
        return True

    def play(self, address: str) -> None:
        self.asked.append(address)
        self.is_playing = True

    def playing(self) -> bool:
        return self.is_playing

    def pause(self) -> None:
        self.paused += 1
        self.is_playing = False

    def now_playing(self) -> tuple[str, str, str]:
        return "Practice mix", "Band", "track"


def with_stand_ins(window: NativeWindow) -> NativeWindow:
    """The window with a tray and a bell that only note what they were asked."""
    window._tray_icon = Tray()
    window._bell = Bell()
    return window


def serve(database: Path, opened: list) -> LocalServer:
    server = LocalServer(database)
    server.start()
    opened.append(server)
    return server


def launch(
    qapp: QApplication, server: LocalServer, name: str, opened: list, *, create: bool
) -> NativeWindow:
    """The app opened on this server: a new account past setup, or a sign-in to an existing one."""
    window = NativeWindow(server.origin)
    opened.append(window)
    window.resize(1280, 860)
    window.show()
    window.username.setText(name)
    window.password.setText(PASSWORD)
    if create:
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(qapp, window)
    else:
        if window.sign_in_button.isHidden():
            window.findChild(QPushButton, "authSwitch").click()
        window.keep_signed_in.setChecked(False)
        window.sign_in_button.click()
        wait_until(qapp, lambda: window.session.preferences is not None and not window.session.busy)
    return with_stand_ins(window)


def at(hour: int, minute: int) -> None:
    """Thursday of the week on screen (the clock's start day), at this time."""
    CLOCK.set(START.replace(hour=hour, minute=minute))


def choose(qapp: QApplication, window: NativeWindow, **preferences: object) -> None:
    window.session.save_preferences(preferences)
    wait_until(
        qapp,
        lambda: not window.session.busy
        and all((window.session.preferences or {}).get(key) == value for key, value in preferences.items()),
    )


def add_practice(qapp: QApplication, window: NativeWindow, **extra: object) -> None:
    window.session.add_block(
        {
            "id": "practice",
            "title": "Guitar practice",
            "kind": "locked",
            "category": "class",
            "start": "18:45",
            "duration_min": 30,
            "days": [3],
            **extra,
        }
    )
    window.session.save()
    settled(qapp, window)


def tick(qapp: QApplication, window: NativeWindow, minute: int) -> None:
    """What the window's poll does every 30 seconds, at 18:mm on the held clock."""
    at(18, minute)
    window.session.check_alerts()
    wait_until(qapp, lambda: not window.session.busy)


def seen(window: NativeWindow) -> dict:
    return {
        "tray": list(window._tray_icon.shown),
        "toast": window.toast.text() if window.toast.isVisible() else "",
    }


def answer_alarm(window: NativeWindow, button: str, heard: list) -> None:
    """Press a button on the alarm when it rings, noting what it said. The alarm's dialog is modal, so
    this runs inside its event loop once the dialog is up."""
    tries = [0]

    def act() -> None:
        tries[0] += 1
        with contextlib.suppress(RuntimeError):
            dialog = window._alarm_dialog
            if dialog is None or not dialog.isVisible():
                if tries[0] < 1000:
                    QTimer.singleShot(0, act)
                return
            words = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
            heard.append(words)
            dialog.findChild(QPushButton, button).click()

    QTimer.singleShot(0, act)
