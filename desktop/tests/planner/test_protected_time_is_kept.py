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


def test_hours_the_engine_refuses_are_not_sent_and_the_status_line_says_what_to_check(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    wait_until(qapp, lambda: session.preferences is not None)
    kept = dict(session.preferences)
    said: list[str] = []
    session.status.connect(said.append)
    meal = {"kind": "meal", "days": [0, 1, 2, 3, 4], "start": "18:00", "duration_min": 30}
    hours = [{"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "21:00"}]
    refused = [
        # Protected time of a kind the app does not have.
        ([{**meal, "kind": "nap"}], hours),
        # Study hours that end before they start.
        ([meal], [{"days": [0], "start": "21:00", "end": "08:00"}]),
        # Study hours on a day that is not one of the seven.
        ([meal], [{"days": [7], "start": "08:00", "end": "21:00"}]),
    ]
    for protected, work in refused:
        said.clear()
        assert session.save_availability(protected, "21:00", work) is False
        assert said == ["Check the days and times of your study hours and protected time."]
        assert not session.busy
        assert session.preferences == kept
    # Protected time alone is checked when Study hours are not sent.
    said.clear()
    assert session.save_availability([{**meal, "start": "18:07"}], "21:00") is False
    assert said == ["Check the days and times of your study hours and protected time."]
