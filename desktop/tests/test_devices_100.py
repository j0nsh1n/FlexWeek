"""Devices in Settings (1.0.0 S7b): a phone pairs and is listed, Remove asks first and revokes, a phone's
change reloads the week unless this window has unsaved edits, and the status dot says what sync is doing."""

from __future__ import annotations

import contextlib
import importlib.util
import re
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
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

    from backend.storage import initialize
    from desktop.native.devices import (
        DOT_WORDS,
        NO_PHONE_WORDS,
        RELAY_SENTENCE,
        UNREACHABLE_WORDS,
        DevicesPanel,
        countdown_words,
        pair_problem,
        seen_words,
        sync_state,
        tries_words,
    )
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


@pytest.fixture()
def desk(qapp: QApplication, server: LocalServer, tmp_path: Path) -> Iterator[NativeWindow]:
    """A signed-in window whose sync service works on the same database as its local server. Only
    loopback addresses are used; no network relay is reached from a test."""
    look_file().unlink(missing_ok=True)
    database = tmp_path / "flexweek.db"
    service = SyncService.start(
        str(database), str(database.parent / "sync" / "device.key"), "Desk", True, "127.0.0.1:0", 1000
    )
    window = NativeWindow(server.origin, sync=service)
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
        service.stop()


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
    assert text.startswith("flexweek://pair?c=" + code.text().replace(" ", ""))
    phone.pair_from_qr(text, PAIR_DEADLINE_MS)
    wait_until(qapp, lambda: listed_phones(panel) == [PHONE_NAME])
    return panel


def test_a_phone_that_pairs_is_listed_on_the_card(
    qapp: QApplication, desk: NativeWindow, phone: SyncService
) -> None:
    panel = pair_a_phone(qapp, desk, phone)
    assert listed_phones(panel) == [PHONE_NAME]
    assert panel.findChild(QLabel, "devicesProblem").text() == ""
    assert not desk.sync_dot.isHidden()
    assert desk.sync_dot.toolTip() == DOT_WORDS["idle"]


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
