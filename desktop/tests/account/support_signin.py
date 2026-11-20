"""What the sign-in tests share: a computer (one database and one kept-session folder) that windows are
launched on, answered in this process by the light app's backend, with no server. The account is made
and signed in on Material's card."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from desktop.native.kept import KeptSession
from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.light_app import ORIGIN, InProcessApi, _client_for, _close
from desktop.tests.logic_support import card_phase, past_recovery, past_setup, sign_up
from desktop.tests.material_support import page_showing
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, look_file, qapp  # noqa: F401

LARGE = {"preset": "default", "knobs": {"text": "large"}}
LARGE_HIGH_CONTRAST = {"preset": "high-contrast", "knobs": {"text": "large"}}


def pump() -> None:
    for _ in range(4):
        QApplication.processEvents()


def page(window: NativeWindow) -> str:
    return page_showing(window)


def system_dark() -> bool:
    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


class Computer:
    """One computer: a database, a kept-session folder, and the windows launched on them."""

    def __init__(self, qapp: QApplication, folder: Path) -> None:
        self.qapp = qapp
        self.api = InProcessApi(folder / "flexweek.db")
        self.kept = KeptSession(folder / "signed-in" / "flexweek.json")
        self.windows: list[NativeWindow] = []

    def launch(self, *, keep_look_file: bool = False) -> NativeWindow:
        """The app opened on this computer, on a clean one unless a test left a look file for it."""
        if not keep_look_file:
            look_file().unlink(missing_ok=True)
        with _client_for(self.api):
            window = NativeWindow(ORIGIN, kept=self.kept)
        window.show()
        self.windows.append(window)
        wait_until(self.qapp, lambda: not window.session.busy, what="the launch settling")
        return window

    def relaunch(self, window: NativeWindow) -> NativeWindow:
        """The app closed and opened again: the first window is gone, the next reads the same files."""
        window.hide()
        return self.launch()

    def create_account(self, window: NativeWindow, name: str) -> None:
        """Make the account and leave setup, on the week."""
        window._account_bridge().setKeepSignedIn(False)
        sign_up(self.qapp, window, name, PASSWORD)
        past_recovery(self.qapp, window)
        past_setup(self.qapp, window)

    def sign_in(self, window: NativeWindow, name: str) -> None:
        """Sign in on Material's card and wait for the week."""
        bridge = window._account_bridge()
        bridge.showSignIn()
        bridge.setUsername(name)
        bridge.setPassword(PASSWORD)
        bridge.submit()
        wait_until(
            self.qapp,
            lambda: window.session.account is not None and bridge.phase == "app" and not window.session.busy,
            what="the week after signing in",
        )
        pump()

    def wear(self, window: NativeWindow, look: dict) -> None:
        window._look = sanitize_look(look)
        window.session.look = window._look
        window._save_look()

    def sign_out(self, window: NativeWindow) -> None:
        window.session.logout()
        wait_until(
            self.qapp,
            lambda: card_phase(window) == "sign-in" and window.session.account is None,
            what="the sign-in page after Log out",
        )
        pump()

    def close(self) -> None:
        for window in reversed(self.windows):
            _close(window)
        self.windows.clear()
        self.api.close()
        look_file().unlink(missing_ok=True)


@pytest.fixture()
def computer(qapp: QApplication, tmp_path: Path) -> Iterator[Computer]:
    made = Computer(qapp, tmp_path)
    yield made
    made.close()


@pytest.fixture()
def signed_out(computer: Computer) -> NativeWindow:
    """The app opened for the first time on a computer: the sign-in card, nobody signed in."""
    return computer.launch()
