"""Protected time, the day cutoff and the work hours a student sets come back from the server as set."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_availability_round_trips_protected_time(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    wait_until(qapp, lambda: session.preferences is not None)
    meal = {"kind": "meal", "days": [0, 1, 2, 3, 4], "start": "18:00", "duration_min": 30}
    hours = [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "08:00", "end": "21:00"}]
    assert session.save_availability([meal], "21:00", hours)
    wait_until(qapp, lambda: not session.busy)
    assert session.preferences is not None
    assert session.preferences["protected"][0]["kind"] == "meal"
    assert session.preferences["day_cutoff"] == "21:00"
    assert session.preferences["work_windows"][0]["start"] == "08:00"
