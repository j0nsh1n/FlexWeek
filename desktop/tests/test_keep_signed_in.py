"""Keep me signed in, against a real local backend. Each launch starts the server on a new port, as
the app does, so a kept session has to work for a server it was not issued by.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import stat
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication

    from desktop.native.kept import KeptSession
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"
TOKEN_LIKE = "A" * 43


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-keep-signed-in-test"])
    yield application


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def page(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


class Launches:
    """Launches of the app against one database, each with its own server, closed at the end."""

    def __init__(self, qapp: QApplication, folder: Path) -> None:
        self.qapp = qapp
        self.database = folder / "flexweek.db"
        self.kept = KeptSession(folder / "signed-in" / "flexweek.json")
        self.servers: list[LocalServer] = []
        self.windows: list[NativeWindow] = []

    def launch(self) -> NativeWindow:
        server = LocalServer(self.database)
        origin = server.start()
        self.servers.append(server)
        window = NativeWindow(origin, kept=self.kept)
        window.show()
        self.windows.append(window)
        return window

    def quit(self, window: NativeWindow) -> None:
        """The app closing: the window goes, nothing is signed out."""
        window.hide()
        self.qapp.processEvents()

    def close(self) -> None:
        for window in self.windows:
            window.hide()
        for server in self.servers:
            with contextlib.suppress(Exception):
                server.stop()


@pytest.fixture()
def launches(qapp: QApplication, tmp_path: Path) -> Iterator[Launches]:
    made = Launches(qapp, tmp_path)
    yield made
    made.close()


def create_account(qapp: QApplication, window: NativeWindow, name: str, *, keep: bool = True) -> None:
    window.username.setText(name)
    window.password.setText(PASSWORD)
    window.keep_signed_in.setChecked(keep)
    window.create_button.click()
    wait_until(qapp, lambda: page(window) == "recoveryPage")
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    past_setup(qapp, window)


def sign_in(qapp: QApplication, window: NativeWindow, name: str, *, keep: bool = True) -> None:
    window.username.setText(name)
    window.password.setText(PASSWORD)
    window.keep_signed_in.setChecked(keep)
    window.sign_in_button.click()
    wait_until(qapp, lambda: page(window) == "weekPage" and not window.session.busy)


def opens_on_sign_in(qapp: QApplication, window: NativeWindow) -> bool:
    # The kept session is tried on the first turn of the event loop and answered by the local server.
    wait_until(qapp, lambda: not window.session.busy)
    for _ in range(20):
        qapp.processEvents()
    return page(window) == "authPage" and window.session.account is None


def test_the_sign_in_card_offers_it_and_it_starts_on(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
    assert window.keep_signed_in.text() == "Keep me signed in on this computer"
    assert window.keep_signed_in.isChecked() is True
    assert window.keep_signed_in.isVisibleTo(window)
    window._toggle_auth_mode()
    assert window.keep_signed_in.isVisibleTo(window), "creating an account offers it too"


def test_the_box_can_be_seen_ticked_or_not(qapp: QApplication, launches: Launches) -> None:
    """Fusion's own box was a faint line that vanished on the white card on the KDE desktop."""
    from PySide6.QtGui import QColor

    window = launches.launch()
    box = window.keep_signed_in
    card = QColor(window.styleSheet().split("QWidget#authCard { background: ")[1].split(";")[0])

    def marked(checked: bool) -> int:
        box.setChecked(checked)
        qapp.processEvents()
        image = box.grab().toImage()
        # The box sits at the left end; its text starts after it.
        return sum(
            1
            for x in range(min(22, image.width()))
            for y in range(image.height())
            if abs(image.pixelColor(x, y).lightness() - card.lightness()) > 60
        )

    assert marked(False) >= 20, "an unticked box is drawn"
    assert marked(True) > marked(False), "a ticked box is filled"


def test_a_kept_session_opens_the_week_at_the_next_launch(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
    create_account(qapp, window, "kept_student")
    assert launches.kept.token() is not None
    assert stat.S_IMODE(launches.kept.path.stat().st_mode) == 0o600
    launches.quit(window)

    later = launches.launch()
    wait_until(qapp, lambda: page(later) == "weekPage" and not later.session.busy)
    assert later.session.account is not None
    assert later.session.account["username"] == "kept_student"
    assert later.account_name.text() == "kept_student"


def test_nothing_is_kept_when_the_box_is_cleared(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
    create_account(qapp, window, "shared_computer", keep=False)
    assert launches.kept.token() is None
    launches.quit(window)
    assert opens_on_sign_in(qapp, launches.launch())


def test_signing_in_without_it_forgets_a_session_kept_before(qapp: QApplication, launches: Launches) -> None:
    """A launch that could not reach its server leaves the kept session in place and shows the card."""
    window = launches.launch()
    create_account(qapp, window, "changed_mind")
    window.session.logout()
    wait_until(qapp, lambda: page(window) == "authPage" and not window.session.busy)
    launches.kept.keep(TOKEN_LIKE)
    sign_in(qapp, window, "changed_mind", keep=False)
    assert launches.kept.token() is None


def test_log_out_forgets_it(qapp: QApplication, launches: Launches) -> None:
    window = launches.launch()
    create_account(qapp, window, "signs_out")
    window.session.logout()
    wait_until(qapp, lambda: page(window) == "authPage" and not window.session.busy)
    assert launches.kept.token() is None
    launches.quit(window)
    assert opens_on_sign_in(qapp, launches.launch())


def test_the_recovery_codes_are_seen_before_anything_is_kept(qapp: QApplication, launches: Launches) -> None:
    """Kept at registration, quitting on the codes page would open the week next time, and the codes
    would never be shown again."""
    window = launches.launch()
    window.username.setText("quits_early")
    window.password.setText(PASSWORD)
    window.create_button.click()
    wait_until(qapp, lambda: page(window) == "recoveryPage")
    assert launches.kept.token() is None
    launches.quit(window)
    assert opens_on_sign_in(qapp, launches.launch())


def test_a_session_the_server_ended_falls_back_to_sign_in(qapp: QApplication, launches: Launches) -> None:
    launches.kept.keep(TOKEN_LIKE)
    window = launches.launch()
    assert opens_on_sign_in(qapp, window)
    assert launches.kept.token() is None, "a dead session is not tried again at every launch"
    assert "sign in" in window.auth_status.text().lower()


def test_a_new_password_keeps_the_new_session(qapp: QApplication, launches: Launches) -> None:
    """Changing the password replaces the session, and the kept one stops working."""
    window = launches.launch()
    create_account(qapp, window, "new_password")
    before = launches.kept.token()
    window.session.change_password(PASSWORD, PASSWORD + "-2")
    wait_until(qapp, lambda: not window.session.busy and window.session.message == "Password replaced.")
    assert launches.kept.token() not in {None, before}
    launches.quit(window)
    later = launches.launch()
    wait_until(qapp, lambda: page(later) == "weekPage" and not later.session.busy)
    assert later.session.account is not None and later.session.account["username"] == "new_password"


def test_a_kept_file_that_is_not_a_session_is_ignored(tmp_path: Path) -> None:
    kept = KeptSession(tmp_path / "kept.json")
    kept.path.write_text('{"token": "abc; Path=/; flexweek_session=other"}')
    assert kept.token() is None
    kept.path.write_text("not json")
    assert kept.token() is None
    with pytest.raises(ValueError):
        kept.keep("bad token\r\nSet-Cookie: x")
