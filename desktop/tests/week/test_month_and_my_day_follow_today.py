"""The date and month the other views show: Month and the mini month follow today across a week
boundary and keep a picked day, My day names the day chosen on its strip, and the month asked for first
is fetched before it is shown."""

from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402

qapp = support_zoom.qapp  # fixtures are found by their name in the test module
window = support_zoom.window






def test_open_week_month_is_prefetched_without_waiting_for_it(
    qapp: QApplication, window: NativeWindow, monkeypatch
) -> None:
    session = window.session
    CLOCK.set(datetime.fromisoformat("2026-10-15T15:40"))
    session.week_start = "2026-10-12"
    session._month_cache.clear()
    session._month_prefetching.clear()
    requests = []
    monkeypatch.setattr(session.client, "request", lambda *args: requests.append(args))

    session._prefetch_open_week_month()

    assert len(requests) == 1
    assert requests[0][0:2] == ("GET", "/api/month?month=2026-10")
    assert session.month_data is None
    requests[0][3]({"month": "2026-10"})
    assert session._month_cache[(str(session.account["id"]), "2026-10")]["month"] == "2026-10"
    session.set_view("month")
    # The month kept is on screen at once, before any answer; it is asked for again all the same,
    # since another week may have changed, and the fresh answer replaces it.
    assert session.month_data == {"month": "2026-10"}
    asked_again = [args for args in requests[1:] if args[1] == "/api/month?month=2026-10"]
    assert len(asked_again) == 1
    asked_again[0][3]({"month": "2026-10", "days": [], "fresh": True})
    assert session.month_data.get("fresh") is True


def test_a_week_from_wednesday_asks_for_the_month_from_wednesday(
    qapp: QApplication, window: NativeWindow, monkeypatch
) -> None:
    session = window.session
    CLOCK.set(datetime.fromisoformat("2026-10-15T15:40"))
    session.follow_first_weekday(2)
    wait_until(qapp, lambda: not session.busy)
    assert session.week_start == "2026-10-14"
    session._month_cache.clear()
    session._month_prefetching.clear()
    requests = []
    monkeypatch.setattr(session.client, "request", lambda *args: requests.append(args))
    session._prefetch_open_week_month()
    session.set_view("month")
    # Both the month on screen and the one asked for ahead name Wednesday (2) as the first day.
    assert [args[1] for args in requests] == ["/api/month?month=2026-10&first_day=2"] * 2


def test_month_keeps_a_picked_day_and_uses_thursday_for_a_week_without_today(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    held = datetime.fromisoformat("2026-09-29T10:20")
    CLOCK.set(held)
    session.open_day("2026-09-30")
    wait_until(qapp, lambda: not session.busy)
    session.set_view("month")
    wait_until(qapp, lambda: session.month_data is not None)
    session.set_view("day")
    wait_until(qapp, lambda: not session.busy)
    assert session.selected_day == "2026-09-30"
    session.set_view("week")
    session.load_week("2026-10-26")
    wait_until(qapp, lambda: not session.busy)
    session.set_view("month")
    wait_until(qapp, lambda: session.month_data is not None)
    assert session.selected_month == "2026-10"
