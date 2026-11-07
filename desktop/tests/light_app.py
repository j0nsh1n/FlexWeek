"""The light app: the real window and the real backend, with no server and no sign-in per test.

The backend is called in this process (no socket, no server thread), and each test opens on a copy
of one account that was signed up and taken past setup once per worker, through the same window, so
it starts where the signed-in `window` fixture of window_support.py did."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl
from PySide6.QtNetwork import QNetworkCookie, QNetworkReply
from PySide6.QtWidgets import QApplication, QPushButton
from shiboken6 import isValid
from starlette.testclient import TestClient

from backend.tests.fake_clock import CLOCK
from desktop.native import controller as controller_module
from desktop.native.client import NativeClient
from desktop.native.kept import KeptSession
from desktop.native.window import NativeWindow
from desktop.tests.logic_support import past_setup
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, free, look_file, still

# Never listened on: the backend checks requests' Origin and Host against it.
ORIGIN = "http://127.0.0.1:8941"


class InProcessApi:
    """The backend app for one database, answering in this process."""

    def __init__(self, database: Path) -> None:
        from backend.app import create_app

        self._client = TestClient(
            create_app(database=database, origin=ORIGIN),
            base_url=ORIGIN,
            raise_server_exceptions=False,
            follow_redirects=False,
        )
        self._client.__enter__()

    def call(
        self, method: str, path: str, body: bytes, headers: dict[str, str]
    ) -> tuple[int, bytes, list[str]]:
        response = self._client.request(method, path, content=body or None, headers=headers)
        # The window's own cookie jar is the one that keeps the session, as with the real server.
        self._client.cookies.clear()
        return response.status_code, response.content, response.headers.get_list("set-cookie")

    def close(self) -> None:
        self._client.__exit__(None, None, None)


class LightClient(NativeClient):
    """NativeClient with every request answered by `api`; its reply comes on the next turn of the
    event loop, as a real one comes later, never inside the call that sent it. A test that needs a
    reply to stay on its way holds them (`hold`) and lets them land (`release`)."""

    def __init__(self, origin: str, parent: QObject | None, api: InProcessApi) -> None:
        super().__init__(origin, parent)
        self.api = api
        # Replies made and not yet handed to the window.
        self.pending = 0
        self._held: list[Callable[[], None]] | None = None

    def hold(self) -> None:
        self._held = []

    def release(self) -> None:
        held, self._held = self._held or [], None
        for answer in held:
            QTimer.singleShot(0, self, answer)

    def _send(
        self,
        method: str,
        path: str,
        encoded: bytes,
        account_id: int | None,
        finish: Callable[[int, bytes, bool], None],
    ) -> QNetworkReply | None:
        jar = self._manager.cookieJar()
        url = QUrl(self.origin + path)
        headers = self.headers(account_id)
        sent = "; ".join(
            f"{bytes(cookie.name().data()).decode()}={bytes(cookie.value().data()).decode()}"
            for cookie in jar.cookiesForUrl(url)
        )
        if sent:
            headers["Cookie"] = sent
        status, body, set_cookies = self.api.call(method, path, encoded, headers)

        def answer() -> None:
            self.pending -= 1
            for raw in set_cookies:
                jar.setCookiesFromUrl(QNetworkCookie.parseCookies(QByteArray(raw.encode("latin-1"))), url)
            finish(status, body, True)

        self.pending += 1
        if self._held is not None:
            self._held.append(answer)
        else:
            QTimer.singleShot(0, self, answer)
        return None


@dataclass(frozen=True)
class Account:
    database: Path
    look: bytes | None
    token: str


_ACCOUNT: Account | None = None


def _copy(source: Path, target: Path) -> None:
    with (
        contextlib.closing(sqlite3.connect(source)) as kept,
        contextlib.closing(sqlite3.connect(target)) as new,
    ):
        kept.backup(new)


@contextlib.contextmanager
def _client_for(api: InProcessApi) -> Iterator[None]:
    """While a window is made, its session's client is a LightClient on `api`."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            controller_module, "NativeClient", lambda origin, parent: LightClient(origin, parent, api)
        )
        yield


def _close(window: NativeWindow) -> None:
    if not isValid(window):
        return  # the test closed and freed it itself
    with contextlib.suppress(RuntimeError):
        window.session.client.reset()
    window.hide()
    free(window)


def account(qapp: QApplication, root: Path) -> Account:
    """The worker's one signed-up account, past setup: made the first time a test asks."""
    global _ACCOUNT
    if _ACCOUNT is not None:
        return _ACCOUNT
    root.mkdir(parents=True, exist_ok=True)
    database = root / "account.db"
    # Made at the clock's start whatever the asking test has set it to, so every worker's account is
    # the same one.
    held = CLOCK.now()
    CLOCK.reset()
    api = InProcessApi(database)
    look_file().unlink(missing_ok=True)
    with _client_for(api):
        window = NativeWindow(ORIGIN)
    window.show()
    try:
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(qapp, window)
        token = window.session.client.session_token()
        assert token, "signing up kept no session"
        look = look_file().read_bytes() if look_file().exists() else None
    finally:
        _close(window)
        api.close()
        CLOCK.set(held)
    _ACCOUNT = Account(database, look, token)
    return _ACCOUNT


def open_light_window(
    qapp: QApplication, tmp_path: Path, made: Account, size: tuple[int, int] | None = None
) -> tuple[NativeWindow, InProcessApi]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "flexweek.db"
    _copy(made.database, database)
    look_file().parent.mkdir(parents=True, exist_ok=True)
    if made.look is None:
        look_file().unlink(missing_ok=True)
    else:
        look_file().write_bytes(made.look)
    api = InProcessApi(database)
    kept = KeptSession(tmp_path / "kept-session")
    kept.keep(made.token)
    with _client_for(api):
        window = NativeWindow(ORIGIN, kept=kept)
    if size is not None:
        window.resize(*size)
    window.show()
    session = window.session
    session.resume()
    wait_until(
        qapp,
        lambda: (
            window._stack.currentWidget().objectName() in {"weekPage", "materialPage"}
            and session.preferences is not None
            and not session.busy
            and not getattr(session.client, "pending", 0)
        ),
        what="the light window opening on the week",
    )
    # As after signing up: the account is new for this sitting (set only now, or setup would open
    # before the preferences that say it was finished), and no session was kept on this computer.
    session.new_account = True
    session.kept = None
    still(window)
    return window, api


class LightWindows:
    """Light windows on one test's account copies, all closed together."""

    def __init__(self, qapp: QApplication, base: Path, folder: Path) -> None:
        """`base` is the worker's own temporary folder (where its one account is kept); `folder` is
        where these windows keep their copies."""
        self._qapp, self._folder = qapp, folder
        self._made = account(qapp, base / "light-account")
        self._opened: list[tuple[NativeWindow, InProcessApi]] = []

    def open(self, size: tuple[int, int] | None = None) -> NativeWindow:
        folder = self._folder / f"window-{len(self._opened)}"
        window, api = open_light_window(self._qapp, folder, self._made, size)
        self._opened.append((window, api))
        return window

    def close(self) -> None:
        for window, api in reversed(self._opened):
            _close(window)
            api.close()
        self._opened.clear()


@pytest.fixture()
def open_light(
    qapp: QApplication,
    tmp_path_factory: pytest.TempPathFactory,
    tmp_path: Path,
) -> Iterator[Callable[..., NativeWindow]]:
    """Opens light windows signed in on the week page, setup skipped, preferences loaded, as
    window_support's `window` does; `size` is the window's before it is first shown. Set the clock
    first when the week's first showing depends on the time. Each is closed when the test ends."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        yield windows.open
    finally:
        windows.close()


@pytest.fixture()
def window(
    qapp: QApplication,
    tmp_path_factory: pytest.TempPathFactory,
    tmp_path: Path,
) -> Iterator[NativeWindow]:
    """A light window at the size a new window has: window_support's `window`, without its server."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        yield windows.open()
    finally:
        windows.close()
