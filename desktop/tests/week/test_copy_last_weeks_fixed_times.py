"""Copying last week's fixed times fetches that week for the copy sheet; it must not leave it parked
as unsaved work."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from desktop.native.calendar import monday_of
from desktop.native.widgets import PreviewDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_weekview import CLASSIC_ONE_DAY
from desktop.tests.window_support import qapp, settled, wait_until  # noqa: F401

LAST_WEEK_FIXED = {
    "id": "soccer",
    "kind": "locked",
    "title": "Soccer",
    "category": "sport",
    "start": "16:00",
    "duration_min": 90,
    "days": [2],
}


def test_copying_last_weeks_fixed_times_does_not_park_it_as_unsaved(
    qapp: QApplication,
    window: NativeWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Last week is fetched for the copy sheet, then opened again as saved work."""
    window._layout = dict(CLASSIC_ONE_DAY)
    session = window.session
    session.add_block(dict(LAST_WEEK_FIXED))
    session.save()
    wait_until(qapp, lambda: not session.busy)
    source = session.week_start
    window.findChild(QPushButton, "nextWeek").click()
    wait_until(qapp, lambda: session.week_start != source and not session.busy)
    settled(qapp, window)
    previous = monday_of((date.fromisoformat(session.week_start) - timedelta(days=7)).isoformat())
    assert previous == source
    assert previous not in session._drafts
    shown: list[bool] = []

    def skip(dialog: PreviewDialog) -> int:
        shown.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(PreviewDialog, "exec", skip)
    window._copy_last_week_fixed()
    wait_until(qapp, lambda: not session.busy and shown)
    assert previous not in session._drafts
    assert previous not in session.unsaved_weeks()
    session.load_week(previous)
    wait_until(qapp, lambda: session.week_start == previous and not session.busy)
    assert "Soccer" in [item["title"] for item in session.blocks]
    assert previous not in session.unsaved_weeks()
