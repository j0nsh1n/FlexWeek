"""A phone's change reloads the week unless this window has unsaved edits; the status dot stays hidden
until a phone is linked."""

from __future__ import annotations

import pytest
from flexweek_engine import SyncService

from desktop.native.window import NativeWindow
from desktop.tests.sync.support import PHONE_NAME, GenerationProxy, devices_panel, pair_a_phone
from desktop.tests.waiting import wait_until

pytest_plugins = ["desktop.tests.sync.support"]


def test_a_phone_change_reloads_the_week_unless_this_window_has_unsaved_edits(
    light_desk: NativeWindow, phone: SyncService, monkeypatch: pytest.MonkeyPatch
) -> None:
    desk = light_desk
    pair_a_phone(desk, phone)
    wait_until(None, lambda: not desk.sync_dot.isHidden())
    # The test makes the ticks itself, so the window's own once-a-second look cannot add one.
    desk._sync_timer.stop()
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


def test_the_status_dot_is_hidden_until_a_phone_is_linked(light_desk: NativeWindow) -> None:
    devices_panel(light_desk)
    light_desk._sync_tick()
    assert light_desk.sync_dot.isHidden()
