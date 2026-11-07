"""The light app opens where signing up and skipping setup on a real server does, so a test moved onto
it checks what it checked before."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import FakeClock
from desktop.native.calendar import monday_of
from desktop.native.window import NativeWindow
from desktop.tests.light_app import account, open_light, open_light_window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, look_file, qapp, server, signed_out, window  # noqa: F401


def seen(opened: NativeWindow) -> dict:
    session = opened.session
    look = json.loads(look_file().read_text(encoding="utf-8")) if look_file().exists() else None
    return {
        "page": opened._stack.currentWidget().objectName(),
        "username": (session.account or {}).get("username"),
        "preferences": session.preferences,
        "blocks": session.blocks,
        "assignments": session.assignments,
        "week": session.week_start,
        "day": session.selected_day,
        "new account": session.new_account,
        "keep signed in": session.keep_signed_in,
        "kept": session.kept,
        "dirty or busy": (session.dirty, session.busy),
        "toast": (opened.toast.isVisible(), opened.toast.text()),
        "look": opened._look,
        "layout": opened._layout,
        "surface": opened._surface,
        "look file": None if look is None else {key: look[key] for key in look if key != "accounts"},
        "size": (opened.width(), opened.height()),
    }


def test_the_light_window_opens_as_a_new_account_past_setup_does(
    qapp: QApplication, window: NativeWindow, open_light: Callable[..., NativeWindow]  # noqa: F811
) -> None:
    # The status line is left out: it says what the last request did, a saved setup on one and the
    # opened week on the other.
    signed_up = seen(window)
    light = seen(open_light())
    assert light == signed_up


def test_what_one_light_window_saves_is_not_in_the_next(
    qapp: QApplication,  # noqa: F811
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    made = account(qapp, tmp_path_factory.getbasetemp() / "light-account")
    first, api = open_light_window(qapp, tmp_path / "first", made)
    first.session.add_block(
        {"id": "piano", "title": "Piano", "kind": "locked", "start": "17:00", "duration_min": 30, "days": [0]}
    )
    first.session.save()
    wait_until(qapp, lambda: not first.session.busy and not first.session.dirty)
    assert [block["id"] for block in first.session.blocks] == ["piano"]
    first.hide()
    free(first)
    api.close()
    second, api = open_light_window(qapp, tmp_path / "second", made)
    try:
        assert second.session.blocks == []
    finally:
        second.hide()
        free(second)
        api.close()


def test_a_light_window_opens_long_after_the_account_was_made(
    qapp: QApplication,  # noqa: F811
    open_light: Callable[..., NativeWindow],  # noqa: F811
    clock: FakeClock,
) -> None:
    clock.move(days=60)
    opened = open_light()
    assert opened.session.week_start == monday_of(clock.today().isoformat())
