"""Setup answers kept while a save is in flight belong to the account that gave them."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication

from desktop.native.client import ApiError
from desktop.server import LocalServer
from desktop.tests.logic_support import PASSWORD, qapp, server, settled, signed_in  # noqa: F401
from desktop.tests.waiting import wait_until

# The fixtures are used by name, so each test's argument list redefines them.
# ruff: noqa: F811


def hold_the_save(session: object) -> None:
    """Start a save and keep its reply. The session stays busy, and the reply is never delivered."""
    real = session.client.request  # type: ignore[attr-defined]

    def request(
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        if method == "POST" and path.startswith("/api/changes"):
            return
        real(method, path, payload, on_success, on_error)

    session.client.request = request  # type: ignore[attr-defined, method-assign, assignment]
    session.save()  # type: ignore[attr-defined]
    assert session.busy  # type: ignore[attr-defined]
    session.client.request = real  # type: ignore[attr-defined, method-assign]


def preference_puts(session: object) -> list[dict]:
    puts: list[dict] = []
    real = session.client.request  # type: ignore[attr-defined]

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

    session.client.request = request  # type: ignore[attr-defined, method-assign, assignment]
    return puts


def test_setup_answers_do_not_cross_a_sign_out(qapp: QApplication, server: LocalServer) -> None:
    """Answers kept while a save is in flight belong to that account. Signing out drops them, and so
    does signing a different account in, so the next flush cannot store them there."""
    session = signed_in(qapp, server.origin, "alice_cross", create=True)
    hold_the_save(session)
    session.keep_setup({"planning_style": "manual", "clock_24h": True})
    assert session.setup_prefs == {"planning_style": "manual", "clock_24h": True}

    session.logout()
    wait_until(qapp, lambda: session.account is None and not session.busy)
    left_at_sign_out = dict(session.setup_prefs)

    session.register("bob_cross", PASSWORD)
    wait_until(qapp, lambda: session.account is not None and not session.busy)
    session.finish_recovery()
    wait_until(qapp, lambda: session.preferences is not None and not session.busy)
    settled(qapp, session)
    puts = preference_puts(session)
    session.flush_setup()
    settled(qapp, session)
    assert puts == []
    assert left_at_sign_out == {}
    assert session.setup_work_windows is None
    assert session.setup_week is False
    bob = session.preferences
    assert bob is not None
    assert bob.get("planning_style", "suggest") == "suggest"
    assert bob.get("clock_24h", False) is False

    hold_the_save(session)
    session.keep_setup({"planning_style": "manual", "clock_24h": True})
    puts = preference_puts(session)
    session.register("carol_cross", PASSWORD)
    wait_until(
        qapp,
        lambda: (
            session.account is not None and session.account["username"] == "carol_cross" and not session.busy
        ),
    )
    assert session.setup_prefs == {}
    assert puts == []
    # The held save would keep this week on screen. Discard it and read the new account's own
    # preferences back: the queued answers must not have been stored for them.
    session.load_week(session.week_start, discard=True)
    wait_until(qapp, lambda: not session.busy)
    settled(qapp, session)
    carol = session.preferences
    assert carol is not None
    assert carol.get("planning_style", "suggest") == "suggest"
    assert carol.get("clock_24h", False) is False
