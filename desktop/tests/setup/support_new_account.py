"""A student who has never signed up: a new account on its own backend, from its recovery codes into
setup, and launches of the app on it.

The light app's `window` starts past setup, on an account made once per worker. Setup is what a new
account sees first, so these tests sign up on an empty backend. It is the light app's own in-process
backend and client, so no server is started and no socket is opened."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPushButton
from shiboken6 import isValid

from desktop.native import controller as controller_module
from desktop.native.kept import KeptSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import ORIGIN, InProcessApi, LightClient
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, look_file

PASSWORD = "a-long-test-password"
# Signing up and signing in hash the password with scrypt, which is slow on purpose.
HASHING_WAIT = 30.0


class Launcher:
    """One empty backend and the windows opened on it, as launches of the app."""

    def __init__(self, qapp: QApplication, folder: Path) -> None:
        self._qapp = qapp
        self._folder = folder
        self.database = folder / "setup.db"
        self.api = InProcessApi(self.database)
        self._windows: list[NativeWindow] = []

    def open(self) -> NativeWindow:
        """A new window, signed out, on this backend."""
        with pytest.MonkeyPatch.context() as patch:
            api = self.api
            patch.setattr(
                controller_module, "NativeClient", lambda origin, parent: LightClient(origin, parent, api)
            )
            kept = KeptSession(self._folder / f"kept-{len(self._windows)}")
            window = NativeWindow(ORIGIN, kept=kept)
        window.resize(1180, 760)
        window.show()
        self._windows.append(window)
        return window

    def quit(self, window: NativeWindow) -> None:
        """Close a window as the student quits the app."""
        self._windows.remove(window)
        _free(window)

    def restart_backend(self) -> None:
        """The server is stopped and started again on the same database."""
        self.api.close()
        self.api = InProcessApi(self.database)

    def close(self) -> None:
        for window in reversed(self._windows):
            _free(window)
        self._windows.clear()
        self.api.close()


def _free(window: NativeWindow) -> None:
    if not isValid(window):
        return
    with contextlib.suppress(RuntimeError):
        window.session.client.reset()
    window.hide()
    free(window)


@pytest.fixture()
def launcher(qapp: QApplication, tmp_path: Path) -> Iterator[Launcher]:
    # Setup writes the look for this computer. Left behind, it would dress every later test's window.
    look_file().unlink(missing_ok=True)
    made = Launcher(qapp, tmp_path)
    try:
        yield made
    finally:
        made.close()
        look_file().unlink(missing_ok=True)


def page(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


def written(qapp: QApplication, window: NativeWindow) -> None:
    """Everything setup kept has reached the backend, and so has the plan and the save that followed."""

    def done() -> bool:
        return (
            not window.session.busy
            and not window._setup_prefs
            and window._setup_work_windows is None
            and not window._setup_week
            and not window.session.dirty
            and not window.session.client.pending
        )

    wait_until(qapp, done, what="setup's answers written")
    # A plan started by the last save, and the save after it, show only once events have run again.
    wait_until(qapp, done, what="the plan and the save after it")


def new_account(qapp: QApplication, launcher: Launcher, name: str) -> NativeWindow:
    """A window that has just signed up as `name` and is on setup's first page."""
    window = launcher.open()
    wait_until(qapp, lambda: page(window) == "authPage", what="the sign-in page")
    sign_up(qapp, window, name)
    return window


def sign_up(qapp: QApplication, window: NativeWindow, name: str) -> None:
    if window.create_button.isHidden():
        window.findChild(QPushButton, "authSwitch").click()
    window.username.setText(name)
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: page(window) == "recoveryPage", HASHING_WAIT, "the recovery codes")
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(
        qapp, lambda: page(window) == "setupPage" and not window.session.busy, HASHING_WAIT, "setup"
    )
    wait_until(qapp, lambda: window.session.preferences is not None, HASHING_WAIT, "the preferences")


def sign_in(qapp: QApplication, launcher: Launcher, name: str) -> NativeWindow:
    """A fresh launch: a new window, signed in to an account that already exists."""
    window = launcher.open()
    wait_until(qapp, lambda: page(window) == "authPage", what="the sign-in page")
    if window.sign_in_button.isHidden():
        window.findChild(QPushButton, "authSwitch").click()
    window.username.setText(name)
    window.password.setText(PASSWORD)
    window.keep_signed_in.setChecked(False)
    window.sign_in_button.click()
    wait_until(
        qapp,
        lambda: window.session.preferences is not None
        and page(window) in {"weekPage", "setupPage", "materialPage"}
        and not window.session.busy
        and not window.session.client.pending,
        HASHING_WAIT,
        "the account's preferences",
    )
    return window


def locked(window: NativeWindow) -> dict[str, tuple[str, str, tuple[int, ...], int]]:
    return {
        block["id"]: (block["title"], block["start"], tuple(block["days"]), block["duration_min"])
        for block in window.session.blocks
        if block.get("kind") == "locked"
    }
