# ruff: noqa: F811
"""The words Bento, Timeline and Mission control print about the week and a running focus session."""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QListWidget  # noqa: E402

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    settled,
    wait_until,
    window,  # noqa: F401
)


def test_summaries_speak_minutes_not_session_counts(qapp: QApplication, window: NativeWindow) -> None:
    sessions = re.compile(r"\b0 sessions?\b")

    def labels() -> list[str]:
        found = [lab.text() for lab in window.findChildren(QLabel) if lab.text()]
        for box in window.findChildren(QListWidget):
            found.extend(box.item(index).text() for index in range(box.count()))
        return found

    window.focus_panel.set_state(window.session)

    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert "This week" in shown
    assert not any(sessions.search(text) for text in shown)

    # Timeline's week in figures: the minutes of homework planned, and how many homework are done.
    window._layout = {"main": "timeline", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert {"1 h", "homework planned", "0 of 1", "done"} <= set(shown)
    assert not any(sessions.search(text) for text in shown)

    click(window, "viewMyDay")
    click(window, "oneFinished")
    settled(qapp, window)
    click(window, "viewWeek")
    window._layout = {"main": "timeline", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert {"1 h", "homework planned", "1 of 1", "done"} <= set(shown)
    assert not any(sessions.search(text) for text in shown)


def test_mission_counts_focus_minutes_while_a_session_runs(qapp: QApplication, window: NativeWindow) -> None:
    """Four minutes into a session Mission control said "0 min · Focusing now". The minutes count while
    the session runs, and a pause keeps what had passed."""
    window._layout = {"main": "mission", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    block = next(b for b in window.session.blocks if b.get("assignment_id"))
    window.session.start_focus(block["id"], 3)
    wait_until(qapp, lambda: window.session.focus is not None)
    CLOCK.move(minutes=4)
    window._refresh_layout()
    qapp.processEvents()
    mission = window.planner.currentWidget()

    def plain(label: QLabel) -> str:
        return re.sub(r"<[^>]+>", "", label.text()).replace("&nbsp;", " ")

    assert plain(mission.findChild(QLabel, "missionFocusValue")) == "4 min"
    assert plain(mission.findChild(QLabel, "missionFocusLine")) == "Focusing now"
    window.session.toggle_focus_pause()
    CLOCK.move(minutes=5)
    window._refresh_layout()
    qapp.processEvents()
    assert plain(mission.findChild(QLabel, "missionFocusValue")) == "4 min"
    assert plain(mission.findChild(QLabel, "missionFocusLine")) == "Focus paused"
