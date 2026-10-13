"""Devices in Settings (1.0.0 S7b): a phone pairs and is listed, Remove asks first and revokes, a phone's
change reloads the week unless this window has unsaved edits, and the status dot says what sync is doing.
The sync service starts only when a phone is linked at launch or when Pair a phone is pressed."""

from __future__ import annotations

import contextlib
import importlib.util
import re
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

pytest_plugins = ["desktop.tests.window_support"]

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from flexweek_engine import SyncError, SyncService  # type: ignore[import-untyped]
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

    from backend.storage import initialize
    from desktop.native import devices
    from desktop.native.devices import (
        DOT_WORDS,
        NO_PHONE_WORDS,
        RELAY_SENTENCE,
        UNREACHABLE_WORDS,
        DevicesPanel,
        PairDialog,
        SyncHost,
        countdown_words,
        dot_colour,
        linked_phone_at_launch,
        pair_problem,
        seen_words,
        sync_state,
        tries_words,
    )
    from desktop.native.feel import FEELS, Context, set_current
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup
    from desktop.tests.window_support import PASSWORD, USERNAME, free, look_file, still, wait_until

PHONE_NAME = "Pixel"
PAIR_DEADLINE_MS = 20_000


def test_the_last_sync_is_said_in_plain_words() -> None:
    seen = int(datetime(2026, 10, 9, 12, 0).timestamp() * 1000)
    assert seen_words(None, seen) == "Not synced yet"
    assert seen_words(str(seen), seen + 30_000) == "Synced just now"
    assert seen_words(str(seen), seen + 2 * 60_000) == "Synced 2 min ago"
    assert seen_words(str(seen), seen + 3 * 3_600_000) == "Synced 3 h ago"
    assert seen_words(str(seen), seen + 3 * 86_400_000) == "Not seen since Friday"


def test_a_failed_call_stays_a_problem_until_one_call_works() -> None:
    quiet = {"syncing": False, "last_error": None, "last_sync_ms": None}
    assert sync_state(quiet, False) == "off"
    assert sync_state(quiet, True) == "idle"
    assert sync_state({**quiet, "syncing": True}, True) == "syncing"
    assert sync_state({**quiet, "last_sync_ms": 5}, True) == "synced"
    assert sync_state({**quiet, "last_sync_ms": 5, "last_error": "could not reach"}, True) == "problem"


def test_the_pairing_sheet_says_its_countdown_tries_and_problems_in_plain_words() -> None:
    assert countdown_words(299) == "Code works for 4:59"
    assert countdown_words(60) == "Code works for 1:00"
    assert tries_words(1) == "1 try left"
    assert tries_words(3) == "3 tries left"
    assert pair_problem("expired") == "That code has expired. Start a new one."
    assert pair_problem("too_many_tries") == "Too many wrong tries. Start a new code."
    assert pair_problem("waiting") == ""


def test_the_relay_sentence_is_the_agreed_one() -> None:
    assert RELAY_SENTENCE == (
        "When your computer is not on the same Wi-Fi, FlexWeek uses a public relay run by n0. "
        "It sees that two devices are talking, not what they send."
    )


def test_a_problem_dot_uses_the_looks_error_colour(qapp: QApplication) -> None:
    set_current(Context(feel=FEELS["plain"], look={}, palette={"error": "#7a1f1f"}, tokens={}, base_sheet=""))
    try:
        assert dot_colour("problem", QPalette()).name() == "#7a1f1f"
    finally:
        set_current(None)


@contextlib.contextmanager
def signed_in_window(qapp: QApplication, server: LocalServer, host: SyncHost) -> Iterator[NativeWindow]:
    """A window on `server` with a new account signed in and set up. Its sync host is `host`."""
    look_file().unlink(missing_ok=True)
    window = NativeWindow(server.origin, sync=host)
    window.show()
    try:
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: window._stack.currentWidget().objectName() == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(qapp, window)
        still(window)
        yield window
    finally:
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        free(window)


@pytest.fixture()
def desk(qapp: QApplication, server: LocalServer, tmp_path: Path) -> Iterator[NativeWindow]:
    """A signed-in window whose sync service works on the same database as its local server. Only
    loopback addresses are used; no network relay is reached from a test."""
    database = tmp_path / "flexweek.db"
    service = SyncService.start(
        str(database), str(database.parent / "sync" / "device.key"), "Desk", True, "127.0.0.1:0", 1000
    )
    host = SyncHost(database)
    host.service = service
    try:
        with signed_in_window(qapp, server, host) as window:
            yield window
    finally:
        service.stop()


@pytest.fixture()
def lazy_desk(
    qapp: QApplication, server: LocalServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[NativeWindow, SyncHost, list[Path]]]:
    """A signed-in window with no sync service yet. Starting one is counted, and it starts on loopback
    only, so no test reaches the network relay."""
    database = tmp_path / "flexweek.db"
    started: list[Path] = []

    def loopback_start(path: Path) -> SyncService:
        started.append(path)
        (path.parent / "sync").mkdir(parents=True, exist_ok=True)
        return SyncService.start(
            str(path), str(path.parent / "sync" / "device.key"), "Desk", True, "127.0.0.1:0", 1000
        )

    monkeypatch.setattr(devices, "start_service", loopback_start)
    host = SyncHost(database)
    try:
        with signed_in_window(qapp, server, host) as window:
            yield window, host, started
    finally:
        host.stop()


@pytest.fixture()
def phone(tmp_path: Path) -> Iterator[SyncService]:
    """A second device on loopback with its own empty database: the phone."""
    database = tmp_path / "phone" / "flexweek.db"
    database.parent.mkdir()
    initialize(database)
    made = SyncService.start(
        str(database), str(database.parent / "sync" / "device.key"), PHONE_NAME, True, "127.0.0.1:0"
    )
    yield made
    made.stop()


def devices_panel(window: NativeWindow) -> DevicesPanel:
    window._open_settings()
    still(window)
    return window._settings.findChild(DevicesPanel)


def listed_phones(panel: DevicesPanel) -> list[str]:
    return [label.text() for label in panel.findChildren(QLabel, "phoneName")]


def pair_a_phone(qapp: QApplication, window: NativeWindow, phone: SyncService) -> DevicesPanel:
    """Pairs `phone` the way a student does: Pair a phone on the card, then the phone reads the text."""
    panel = devices_panel(window)
    panel.pair_button.click()
    sheet = panel.dialog
    code = sheet.findChild(QLabel, "pairCode")
    wait_until(qapp, lambda: re.fullmatch(r"\d{4} \d{4}", code.text()) is not None)
    text = sheet.findChild(QLineEdit, "pairQr").text()
    assert text.startswith("flexweek://pair/2?c=" + code.text().replace(" ", ""))
    phone.pair_from_qr(text, PAIR_DEADLINE_MS)
    wait_until(qapp, lambda: listed_phones(panel) == [PHONE_NAME])
    return panel


def test_a_phone_that_pairs_is_listed_on_the_card(
    qapp: QApplication, desk: NativeWindow, phone: SyncService
) -> None:
    panel = pair_a_phone(qapp, desk, phone)
    assert listed_phones(panel) == [PHONE_NAME]
    assert panel.findChild(QLabel, "devicesProblem").text() == ""
    wait_until(qapp, lambda: desk.sync_dot.toolTip() == DOT_WORDS["idle"])
    assert not desk.sync_dot.isHidden()


def test_remove_asks_first_then_revokes_the_phone(
    qapp: QApplication, desk: NativeWindow, phone: SyncService
) -> None:
    panel = pair_a_phone(qapp, desk, phone)
    panel.findChild(QPushButton, "removePhone").click()
    panel.dialog.findChild(QPushButton, "keepPhone").click()
    qapp.processEvents()
    assert listed_phones(panel) == [PHONE_NAME], "keeping the phone leaves it linked"

    panel.findChild(QPushButton, "removePhone").click()
    panel.dialog.findChild(QPushButton, "confirmRemove").click()
    wait_until(qapp, lambda: listed_phones(panel) == [])
    assert [label.text() for label in panel.findChildren(QLabel)].count(NO_PHONE_WORDS) == 1
    with pytest.raises(SyncError) as refused:
        phone.sync_once(desk._sync.device_id(), 10_000)
    assert refused.value.kind == "not_paired"


def test_sync_now_with_a_linked_phone_reports_no_problem(
    qapp: QApplication, desk: NativeWindow, phone: SyncService
) -> None:
    panel = pair_a_phone(qapp, desk, phone)
    panel.findChild(QPushButton, "syncNow").click()
    wait_until(qapp, lambda: desk.sync_dot.toolTip() == DOT_WORDS["synced"])
    assert panel.findChild(QLabel, "devicesProblem").text() == ""
    assert UNREACHABLE_WORDS not in {label.text() for label in panel.findChildren(QLabel)}


class GenerationProxy:
    """The real service, with a generation the test can raise: a phone's batch is not needed to show
    what the window does when one arrives."""

    def __init__(self, real: SyncService) -> None:
        self.real = real
        self.raised = 0

    def generation(self) -> int:
        return self.real.generation() + self.raised

    def __getattr__(self, name: str) -> object:
        return getattr(self.real, name)


def test_a_phone_change_reloads_the_week_unless_this_window_has_unsaved_edits(
    qapp: QApplication, desk: NativeWindow, phone: SyncService, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair_a_phone(qapp, desk, phone)
    wait_until(qapp, lambda: not desk.sync_dot.isHidden())
    loads: list[dict] = []
    monkeypatch.setattr(desk.session, "load_week", lambda *args, **kwargs: loads.append(kwargs))
    proxy = GenerationProxy(desk._sync)
    desk._sync = proxy
    proxy.raised = 1
    desk._sync_tick()
    assert loads == [{"discard": True, "said": f"Updated from {PHONE_NAME}."}]

    desk.session.dirty = True
    proxy.raised = 2
    desk._sync_tick()
    assert len(loads) == 1, "unsaved edits are not thrown away by a phone's change"
    assert desk.session.conflict is True
    desk.session.dirty = False
    desk.session.conflict = False


def test_the_status_dot_is_hidden_until_a_phone_is_linked(desk: NativeWindow) -> None:
    devices_panel(desk)
    desk._sync_tick()
    assert desk.sync_dot.isHidden()


def database_with_phone(database: Path, revoked: int) -> None:
    """A database that has run sync once and holds one phone, removed (revoked 1) or not (0)."""
    initialize(database)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users(username, password_hash) VALUES ('ada', 'not-a-real-hash')")
    (database.parent / "sync").mkdir(exist_ok=True)
    running = SyncService.start(
        str(database), str(database.parent / "sync" / "device.key"), "Desk", True, "127.0.0.1:0", 1000
    )
    running.stop()
    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO sync_peer"
            "(user_id, peer_device_id, endpoint_id, name, paired_at, last_seen, revoked) "
            "VALUES (1, 'phone-1', 'endpoint-1', ?, '2026-10-13T00:00:00Z', NULL, ?)",
            (PHONE_NAME, revoked),
        )


def test_a_fresh_database_starts_no_sync_service_at_launch(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "flexweek.db"
    initialize(database)
    started: list[Path] = []
    monkeypatch.setattr(devices, "start_service", lambda path: started.append(path))
    host = SyncHost(database)
    host.start_if_paired()
    assert not host.starting, "no start was asked for"
    qapp.processEvents()
    assert started == []
    assert host.service is None


def test_a_database_whose_only_phone_was_removed_starts_no_service(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "flexweek.db"
    database_with_phone(database, revoked=1)
    assert linked_phone_at_launch(database) is False
    started: list[Path] = []
    monkeypatch.setattr(devices, "start_service", lambda path: started.append(path))
    host = SyncHost(database)
    host.start_if_paired()
    assert not host.starting
    qapp.processEvents()
    assert started == []


def test_a_database_with_a_linked_phone_starts_the_service_at_launch(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "flexweek.db"
    database_with_phone(database, revoked=0)
    assert linked_phone_at_launch(database) is True
    started: list[Path] = []
    monkeypatch.setattr(devices, "start_service", lambda path: started.append(path))
    host = SyncHost(database)
    host.start_if_paired()
    wait_until(qapp, lambda: started)
    assert started == [database]


def test_asking_for_the_service_twice_starts_it_once(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[tuple] = []
    monkeypatch.setattr(devices, "run_off_ui", lambda owner, work, done: starts.append((work, done)))
    host = SyncHost(tmp_path / "flexweek.db")
    host.ensure(lambda service: None)
    host.ensure(lambda service: None)
    assert len(starts) == 1, "a second ask waits for the first start instead of starting another"


def test_the_card_before_any_service_offers_pair_a_phone(
    qapp: QApplication, lazy_desk: tuple[NativeWindow, SyncHost, list[Path]]
) -> None:
    window, host, started = lazy_desk
    panel = devices_panel(window)
    assert host.service is None
    assert started == []
    assert listed_phones(panel) == []
    assert NO_PHONE_WORDS in {label.text() for label in panel.findChildren(QLabel)}
    assert panel.pair_button.isEnabled()
    assert not panel.sync_button.isEnabled()
    assert window.sync_dot.isHidden()


def test_pressing_pair_starts_the_service_once_and_opens_the_pairing_sheet(
    qapp: QApplication, lazy_desk: tuple[NativeWindow, SyncHost, list[Path]]
) -> None:
    window, host, started = lazy_desk
    panel = devices_panel(window)
    panel.pair_button.click()
    assert not panel.pair_button.isEnabled(), "Pair is off while the service starts"
    panel.pair_button.click()
    wait_until(qapp, lambda: isinstance(panel.dialog, PairDialog))
    assert len(started) == 1
    assert host.service is not None
    code = panel.dialog.findChild(QLabel, "pairCode")
    wait_until(qapp, lambda: re.fullmatch(r"\d{4} \d{4}", code.text()) is not None)
    panel.dialog.reject()
