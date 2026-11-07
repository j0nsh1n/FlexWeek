"""The words Settings > Devices and the sync status use: when a phone last synced, what the sync
status is, the pairing sheet's countdown and problems, the clock warning and the relay sentence."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.devices import (
    RELAY_SENTENCE,
    DevicesPanel,
    clock_warning_words,
    countdown_words,
    pair_problem,
    seen_words,
    sync_state,
    tries_words,
)

pytest_plugins = ["desktop.tests.window_support"]


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


def test_clock_skewed_changes_are_reported_only_when_the_count_is_positive() -> None:
    assert clock_warning_words(0) == ""
    assert clock_warning_words(1) == "Your phone's clock looks wrong. 1 change was held back."
    assert clock_warning_words(3) == "Your phone's clock looks wrong. 3 changes were held back."


def test_the_relay_sentence_is_the_agreed_one() -> None:
    assert RELAY_SENTENCE == (
        "When your computer isn't on the same Wi-Fi, FlexWeek uses a public relay run by n0. "
        "It sees that two devices are talking, not what they send."
    )


def test_the_devices_card_shows_and_clears_the_clock_warning(qapp: QApplication) -> None:
    panel = DevicesPanel(None, lambda: 1)
    warning = panel.findChild(QLabel, "clockWarning")
    assert warning is not None and warning.isHidden()

    panel._synced(
        [("phone-a", {"clock_skewed": 1}, None), ("phone-b", {"clock_skewed": 2}, None)],
        None,
    )
    assert warning.text() == "Your phone's clock looks wrong. 3 changes were held back."
    assert not warning.isHidden()

    panel._synced([("phone-a", {"clock_skewed": 0}, None)], None)
    assert warning.isHidden()
