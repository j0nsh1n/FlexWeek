"""Setup's answers leave one write at a time: preferences, then study hours, then the week. Answers
kept before the preferences have arrived go out once they do."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from desktop.native.client import ApiError
from desktop.native.controller import NativeSession
from desktop.tests.planner.session_without_a_window import settled, sign_up  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


def test_setup_writes_stay_in_order(qapp: QApplication, sign_up: Callable[[str], NativeSession]) -> None:
    """Preferences, then study hours, then the week. A second request would replace the first."""
    session = sign_up("setup_order")
    assert session.preferences is not None
    real = session.client.request
    order: list[str] = []
    availability: list[object] = []
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
        counted = (method == "PUT" and path.startswith("/api/preferences")) or (
            method == "POST" and path.startswith("/api/changes")
        )
        if not counted:
            real(method, path, payload, on_success, on_error)
            return
        inflight += 1
        peak = max(peak, inflight)
        order.append(session.message)
        if session.message == "Saving availability…":
            availability.append((payload or {}).get("work_windows"))

        def done(data: dict, then: Callable[[dict], None] = on_success) -> None:
            nonlocal inflight
            inflight -= 1
            then(data)

        def failed(error: ApiError, then: Callable[[ApiError], None] = on_error) -> None:
            nonlocal inflight
            inflight -= 1
            then(error)

        real(method, path, payload, done, failed)

    session.client.request = request  # type: ignore[method-assign, assignment]
    window = [{"days": [0, 1, 2, 3, 4], "start": "15:00", "end": "18:00"}]
    session.keep_setup(
        {"planning_style": "auto", "clock_24h": True},
        work_windows=window,
        save_week=True,
    )
    wait_until(
        qapp,
        lambda: (
            not session.setup_prefs
            and session.setup_work_windows is None
            and not session.setup_week
            and not session.busy
            and inflight == 0
        ),
    )
    settled(qapp, session)
    assert peak == 1, order
    assert order == ["Saving preferences…", "Saving availability…", "Saving…"]
    assert availability == [window]
    assert session.preferences["planning_style"] == "auto"
    assert session.preferences["clock_24h"] is True


def test_setup_answers_are_saved_when_preferences_arrive(
    qapp: QApplication, sign_up: Callable[[str], NativeSession]
) -> None:
    """Answers kept while preferences are still absent go out once that load finishes."""
    session = sign_up("prefs_late")
    assert session.preferences is not None
    session.preferences = None
    puts: list[dict] = []
    real = session.client.request

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "PUT" and path.startswith("/api/preferences"):
            puts.append(dict(payload or {}))
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[method-assign, assignment]
    session.keep_setup({"planning_style": "manual", "clock_24h": True})
    assert session.setup_prefs == {"planning_style": "manual", "clock_24h": True}
    assert puts == []
    session._fetch_preferences()
    wait_until(qapp, lambda: session.preferences is not None)
    settled(qapp, session)
    assert [item["planning_style"] for item in puts] == ["manual"]
    assert [item["clock_24h"] for item in puts] == [True]
    assert session.setup_prefs == {}
