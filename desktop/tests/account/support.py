"""What the account tests share: the Material card helpers, and launches of the app on a database of
their own (the light app answers on the window's thread).

`Launches`, `launches`, `kept`, `launched` and `page` open the app as it runs, its answers coming from
worker threads, for the tests of other areas that still import them; the account tests use
`LightLaunches`."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from backend.storage import initialize
from desktop.native.kept import KeptSession
from desktop.native.window import NativeWindow
from desktop.tests.light_app import InProcessApi, _client_for, _close
from desktop.tests.material_support import page_showing
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, database, free, look_file, qapp  # noqa: F401

OTHER_PASSWORD = "another-long-password"
WRONG_PASSWORD = "not-the-right-password"


class LightLaunches:
    """Launches of the app against one database, answered in this process, each window with the kept
    session file given to it (the launches' own by default)."""

    def __init__(
        self, qapp: QApplication, folder: Path, size: tuple[int, int] | None = None
    ) -> None:
        self.qapp = qapp
        self.size = size
        self.database = folder / "flexweek.db"
        self.kept = KeptSession(folder / "signed-in" / "flexweek.json")
        self.api = InProcessApi(self.database)
        self.windows: list[NativeWindow] = []

    def launch(self, kept: KeptSession | None = None, size: tuple[int, int] | None = None) -> NativeWindow:
        with _client_for(self.api):
            window = NativeWindow(self.database, kept=self.kept if kept is None else kept)
        if (size or self.size) is not None:
            window.resize(*(size or self.size))
        window.show()
        self.windows.append(window)
        wait_until(self.qapp, lambda: not window.session.busy)
        return window

    @contextlib.contextmanager
    def launched(
        self, kept: KeptSession | None = None, size: tuple[int, int] | None = None
    ) -> Iterator[NativeWindow]:
        """One launch that is closed when the block ends, so the next launch starts after it."""
        window = self.launch(kept, size)
        try:
            yield window
        finally:
            _close(window)
            self.windows = [other for other in self.windows if other is not window]

    def close(self) -> None:
        for window in reversed(self.windows):
            _close(window)
        self.windows.clear()
        self.api.close()


@pytest.fixture()
def light_launches(qapp: QApplication, tmp_path: Path) -> Iterator[LightLaunches]:
    made = LightLaunches(qapp, tmp_path)
    yield made
    made.close()


@pytest.fixture()
def material_launches(qapp: QApplication, tmp_path: Path) -> Iterator[LightLaunches]:
    """Material is the saved surface on this computer."""
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps({"surface": "material"}) + "\n")
    made = LightLaunches(qapp, tmp_path, size=(1280, 800))
    yield made
    made.close()
    look_file().unlink(missing_ok=True)


def page(window: NativeWindow) -> str:
    return page_showing(window)


@pytest.fixture()
def kept(tmp_path: Path) -> KeptSession:
    return KeptSession(tmp_path / "signed-in" / "flexweek.json")


@contextlib.contextmanager
def launched(database: Path, kept: KeptSession) -> Iterator[NativeWindow]:
    window = NativeWindow(database, kept=kept)
    window.show()
    try:
        yield window
    finally:
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        free(window)




# The Material sign-in, recovery and setup card, driven through its bridge.


class Launches:
    """Launches of the app against one database, as the app runs."""

    def __init__(self, qapp: QApplication, folder: Path) -> None:
        self.qapp = qapp
        self.database = folder / "flexweek.db"
        initialize(self.database)
        self.kept = KeptSession(folder / "signed-in" / "flexweek.json")
        self.windows: list[NativeWindow] = []

    def launch(self) -> NativeWindow:
        window = NativeWindow(self.database, kept=self.kept)
        window.resize(1280, 800)
        window.show()
        self.windows.append(window)
        for _ in range(40):
            self.qapp.processEvents()
        return window

    def close(self) -> None:
        for window in self.windows:
            with contextlib.suppress(RuntimeError):
                window.session.client.reset()
            window.hide()


@pytest.fixture()
def launches(qapp: QApplication, tmp_path: Path) -> Iterator[Launches]:
    """Material is the saved surface on this computer."""
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps({"surface": "material"}) + "\n")
    made = Launches(qapp, tmp_path)
    yield made
    made.close()
    look_file().unlink(missing_ok=True)


def account(window: NativeWindow):
    bridge = window._account_bridge()
    assert bridge is not None
    return bridge


def root_of(window: NativeWindow) -> QObject:
    root = window._material_page.root
    assert root is not None
    return root


def qml(window: NativeWindow, name: str) -> QObject:
    found = root_of(window).findChild(QObject, name)
    assert found is not None, name
    return found


def visuals(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    if not hasattr(item, "childItems"):
        return found
    for child in item.childItems():
        found.append(child)
        found.extend(visuals(child))
    return found


def named(window: NativeWindow, name: str) -> list[QObject]:
    return [item for item in visuals(root_of(window)) if str(item.objectName()) == name]


def shown(window: NativeWindow, name: str) -> bool:
    """A named QML item that is on screen, including through a hidden parent."""
    for item in named(window, name):
        if hasattr(item, "isVisible"):
            if item.isVisible():
                return True
            continue
        if bool(item.property("visible")):
            return True
    return False


def pump(qapp: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qapp.processEvents()


def fill(window: NativeWindow, name: str, password: str = PASSWORD) -> None:
    bridge = account(window)
    bridge.setUsername(name)
    bridge.setPassword(password)


def create(qapp: QApplication, window: NativeWindow, name: str, *, keep: bool = True) -> list[str]:
    """Register on the Material card and stop on the recovery codes. Returns the codes."""
    bridge = account(window)
    bridge.showCreate()
    fill(window, name)
    bridge.setKeepSignedIn(keep)
    bridge.submit()
    wait_until(qapp, lambda: bridge.phase == "recovery")
    return bridge.codes


def through_recovery(qapp: QApplication, window: NativeWindow) -> None:
    bridge = account(window)
    bridge.setRecoveryAck(True)
    wait_until(qapp, lambda: bridge.recoveryReady)
    bridge.finishRecovery()
    wait_until(qapp, lambda: bridge.phase == "setup")


def settle(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    wait_until(
        qapp,
        lambda: not session.busy
        and not session.setup_prefs
        and session.setup_work_windows is None
        and not session.setup_week,
    )
    pump(qapp)


def skip_setup(qapp: QApplication, window: NativeWindow) -> None:
    bridge = account(window)
    bridge.setupSkipAll()
    wait_until(qapp, lambda: bridge.phase == "app")
    settle(qapp, window)


def sign_out(qapp: QApplication, window: NativeWindow) -> None:
    window.session.logout()
    wait_until(qapp, lambda: account(window).phase == "sign-in" and window.session.account is None)
