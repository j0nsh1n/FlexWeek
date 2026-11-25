# ruff: noqa: F811
"""Settings > Phone & sync in Material 3 lists each linked phone with when it last synced and lets the
student remove it (after asking), sync now, and read the single-word status, the clock warning and the
problem line."""

from __future__ import annotations

from typing import Any

import pytest
from flexweek_engine import SyncService
from PySide6.QtWidgets import QApplication

from desktop.native.settings_copy import DOT_WORDS, RELAY_SENTENCE, UNREACHABLE_WORDS
from desktop.native.window import NativeWindow
from desktop.tests.settings.support_material_settings import (
    _click,
    _named,
    _open_settings,
    _panel,
    _pump,
)
from desktop.tests.sync.support import PAIR_DEADLINE_MS, PHONE_NAME
from desktop.tests.waiting import wait_until

pytest_plugins = ["desktop.tests.sync.support"]


def _pair(window: NativeWindow, phone: SyncService) -> None:
    service = window._sync_host.service
    offer = service.pair_start(int(window.session.account["id"]))
    phone.pair_from_qr(offer["qr"], PAIR_DEADLINE_MS)
    wait_until(None, lambda: [row["name"] for row in window._linked_phones()] == [PHONE_NAME])


def _rows(window: NativeWindow) -> list[dict[str, Any]]:
    return list(_panel(window).property("state")["phoneRows"])


def test_a_linked_phone_is_listed_with_when_it_last_synced(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService
) -> None:
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    assert _rows(window) == []
    assert _named(root, "syncStatusWord")[0].property("text") == "Not linked"
    assert _named(root, "note_relayNote")[0].property("text") == RELAY_SENTENCE
    _pair(window, phone)
    _panel(window)._publish()
    _pump(qapp)
    rows = _rows(window)
    assert [row["name"] for row in rows] == [PHONE_NAME]
    assert rows[0]["seen"] == "Synced just now", "paired a moment ago"
    row = _named(root, f"row_phone_{rows[0]['id']}")[0]
    assert str(row.property("title")) == PHONE_NAME
    assert str(row.property("subtitle")) == "Synced just now"
    assert str(_named(root, f"phone_{rows[0]['id']}")[0].property("kind")) == "danger-outlined"


def test_remove_asks_first_and_keeping_the_phone_leaves_it_linked(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService
) -> None:
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    _pair(window, phone)
    _panel(window)._publish()
    _pump(qapp)
    _click(qapp, window, _named(root, f"phone_{_rows(window)[0]['id']}")[0])
    state = _panel(window).property("state")
    assert state["askRemove"] is True and state["removeName"] == PHONE_NAME
    assert _panel(window).property("promptOpen") is True
    _panel(window).answerRemovePhone("keep")
    assert _panel(window).property("state")["askRemove"] is False
    _pump(qapp)
    assert [row["name"] for row in window._linked_phones()] == [PHONE_NAME]


def test_confirming_removes_the_phone_and_it_can_no_longer_sync(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService
) -> None:
    from flexweek_engine import SyncError

    window = light_desk
    _open_settings(qapp, window, "sync")
    _pair(window, phone)
    _panel(window)._publish()
    _panel(window).askRemovePhone(_rows(window)[0]["id"])
    _panel(window).answerRemovePhone("remove")
    wait_until(None, lambda: window._linked_phones() == [] and _rows(window) == [])
    with pytest.raises(SyncError) as refused:
        phone.sync_once(window._sync.device_id(), 10_000)
    assert refused.value.kind == "not_paired"


def test_remove_ignores_an_unknown_phone(qapp: QApplication, light_desk: NativeWindow) -> None:
    _open_settings(qapp, light_desk, "sync")
    _panel(light_desk).askRemovePhone("no-such-device")
    assert _panel(light_desk).property("state")["askRemove"] is False


def test_sync_now_reports_the_status_and_no_problem(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService
) -> None:
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    assert not _named(root, "row_syncNow")[0].property("visible"), "no phone, nothing to sync"
    _pair(window, phone)
    _panel(window)._publish()
    _pump(qapp)
    assert _named(root, "row_syncNow")[0].property("visible")
    _click(qapp, window, _named(root, "syncNow")[0])
    wait_until(None, lambda: _panel(window).property("state")["syncWords"] == DOT_WORDS["synced"])
    state = _panel(window).property("state")
    assert state["syncStatusWord"] == "Synced" and state["syncStatusTone"] == "ok"
    assert str(_named(root, "syncStatusWord")[0].property("text")) == "Synced"
    assert state["syncProblem"] == "" and state["clockWarning"] == "" and state["syncBusy"] is False


def test_a_phone_that_cannot_be_reached_shows_the_problem_line(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    _pair(window, phone)
    phone.stop()
    _panel(window)._publish()
    _panel(window).syncNow()
    wait_until(None, lambda: _panel(window).property("state")["syncProblem"] != "", timeout=40)
    assert _panel(window).property("state")["syncProblem"] in (UNREACHABLE_WORDS,) or str(
        _panel(window).property("state")["syncProblem"]
    ).startswith("Sync failed")
    assert _panel(window).property("state")["syncStatusWord"] == "Not synced"
    assert _named(root, "note_syncProblem")[0].property("visible")


def test_the_clock_warning_is_said_when_changes_were_held_back(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService
) -> None:
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    _panel(window)._synced([("phone", {"clock_skewed": 2}, None)], None)
    assert _panel(window).property("state")["clockWarning"] == (
        "Your phone's clock looks wrong. 2 changes were held back."
    )
    assert _named(root, "note_clockWarning")[0].property("visible")
    _panel(window)._synced([("phone", {"clock_skewed": 0}, None)], None)
    assert _panel(window).property("state")["clockWarning"] == ""


def test_failed_phone_removal_does_not_override_healthy_sync_status_and_newer_sync_clears_old_error(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 8: removal failure shows its own note without flipping Synced to Not synced, and a newer
    successful service sync clears a stale manual sync error."""
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    _pair(window, phone)
    panel = _panel(window)
    panel._publish()
    _pump(qapp)

    fake_status = {"syncing": False, "last_error": None, "last_sync_ms": 1000}
    monkeypatch.setattr(window._sync, "status", lambda: dict(fake_status))
    panel._publish()
    assert panel.property("state")["syncStatusWord"] == "Synced"

    # A failed removal writes removeError but leaves Synced intact.
    monkeypatch.setattr(
        window.session, "unlink_phone", lambda _dev_id, done: done(None, RuntimeError("denied"))
    )
    panel.askRemovePhone(_rows(window)[0]["id"])
    panel.answerRemovePhone("remove")
    _pump(qapp)
    state = panel.property("state")
    assert "Could not remove" in state["removeError"]
    assert state["syncStatusWord"] == "Synced"
    assert _named(root, "note_removeError")[0].property("visible") is True

    # A failed manual sync shows Not synced until a newer automatic sync succeeds.
    panel._synced(None, RuntimeError("offline"))
    assert panel.property("state")["syncStatusWord"] == "Not synced"
    fake_status["last_sync_ms"] = 2000
    panel._publish()
    assert panel.property("state")["syncProblem"] == ""
    assert panel.property("state")["syncStatusWord"] == "Synced"


def test_sync_status_card_wraps_controls_at_phone_width_and_large_text(
    qapp: QApplication, light_desk: NativeWindow, phone: SyncService
) -> None:
    """Finding 4: at 320 px and Large text with a linked phone, the title keeps usable width and controls
    wrap."""
    window = light_desk
    root = _open_settings(qapp, window, "sync")
    _pair(window, phone)
    panel = _panel(window)
    panel.setTextSize("large")
    window.resize(320, 640)
    panel._publish()
    _pump(qapp, 15)
    title_col = _named(root, "syncStatusTitleCol")[0]
    controls = _named(root, "syncStatusControls")[0]
    assert float(title_col.width()) >= 160
    assert float(controls.y()) >= float(title_col.y()) + float(title_col.height()) - 1
    panel.setTextSize("normal")
    window.resize(1280, 800)
    _pump(qapp)
