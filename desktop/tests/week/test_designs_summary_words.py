# ruff: noqa: F811
"""The words Bento, Timeline and Mission control print about the week and a running focus session."""

from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel, QListWidget  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    settled,
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

    assignment = next(b for b in window.session.blocks if b.get("assignment_id"))["assignment_id"]
    window._finish_homework(assignment)
    settled(qapp, window)
    click(window, "viewWeek")
    window._layout = {"main": "timeline", "day": "one", "options": {}}
    window._on_week()
    qapp.processEvents()
    shown = labels()
    assert {"1 h", "homework planned", "1 of 1", "done"} <= set(shown)
    assert not any(sessions.search(text) for text in shown)


