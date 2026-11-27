"""Flipping two Settings switches quickly before the first save answers keeps both after reload,
and a failed first save still says so while applying the queued second switch on top of the last
saved preferences (roadmap R2)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from desktop.native.client import ApiError
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _click,
    _named,
    _open_settings,
    _panel,
    _prefs,
    _pump,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def _state(window: NativeWindow) -> dict:
    return dict(_panel(window).property("state"))


def test_flipping_two_settings_switches_before_first_save_answers_keeps_both_after_reload(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "alerts")
    session = window.session
    assert _state(window)["reminderSound"] is True
    assert _state(window)["endChime"] is False

    real = session.client.request
    held: list[Callable[[], None]] = []
    puts: list[dict] = []
    inflight = 0
    peak = 0

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        nonlocal inflight, peak
        if not (method == "PUT" and path.startswith("/api/preferences")):
            real(method, path, payload, on_success, on_error)
            return
        puts.append(dict(payload or {}))
        inflight += 1
        peak = max(peak, inflight)

        def done(data: dict, then: Callable[[dict], None] = on_success) -> None:
            nonlocal inflight
            inflight -= 1
            then(data)

        def failed(error: ApiError, then: Callable[[ApiError], None] = on_error) -> None:
            nonlocal inflight
            inflight -= 1
            then(error)

        if len(puts) == 1:
            held.append(lambda: real(method, path, payload, done, failed))
            return
        real(method, path, payload, done, failed)

    session.client.request = request  # type: ignore[method-assign, assignment]
    try:
        _click(qapp, window, _named(root, "reminderSound")[0])
        wait_until(qapp, lambda: len(held) == 1)
        _click(qapp, window, _named(root, "endChime")[0])
        _pump(qapp, 10)

        # Second switch waited for the first PUT; UI already shows both flipped.
        assert len(puts) == 1
        assert _state(window)["reminderSound"] is False
        assert _state(window)["endChime"] is True

        held.pop()()
        wait_until(qapp, lambda: len(puts) == 2 and inflight == 0 and not session.busy)
    finally:
        session.client.request = real  # type: ignore[method-assign]

    assert peak == 1
    assert puts[1]["reminder_sound"] is False
    assert puts[1]["end_chime"] is True

    # Reload from storage and verify both changes persisted.
    session.preferences = None
    session._fetch_preferences()
    wait_until(qapp, lambda: session.preferences is not None)
    assert _prefs(window).get("reminder_sound") is False
    assert _prefs(window).get("end_chime") is True
    assert _state(window)["reminderSound"] is False
    assert _state(window)["endChime"] is True


def test_failed_first_settings_save_says_so_and_still_saves_queued_second_switch(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "alerts")
    session = window.session
    assert _state(window)["reminderSound"] is True
    assert _state(window)["endChime"] is False

    real = session.client.request
    held_fail: list[Callable[[], None]] = []
    puts: list[dict] = []

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if not (method == "PUT" and path.startswith("/api/preferences")):
            real(method, path, payload, on_success, on_error)
            return
        puts.append(dict(payload or {}))
        if len(puts) == 1:
            held_fail.append(lambda: on_error(ApiError(500, "Could not save preferences.")))
            return
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[method-assign, assignment]
    try:
        _click(qapp, window, _named(root, "reminderSound")[0])
        wait_until(qapp, lambda: len(held_fail) == 1)
        _click(qapp, window, _named(root, "endChime")[0])
        _pump(qapp, 10)

        held_fail.pop()()
        wait_until(qapp, lambda: len(puts) == 2 and not session.busy)
        _pump(qapp, 10)
    finally:
        session.client.request = real  # type: ignore[method-assign]

    assert _state(window)["notice"] == "Couldn't save that change. Try again."
    assert puts[1]["reminder_sound"] is True
    assert puts[1]["end_chime"] is True

    session.preferences = None
    session._fetch_preferences()
    wait_until(qapp, lambda: session.preferences is not None)
    assert _prefs(window).get("reminder_sound") is True
    assert _prefs(window).get("end_chime") is True
    assert _state(window)["reminderSound"] is True
    assert _state(window)["endChime"] is True
