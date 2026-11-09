"""Running late says where each block goes in words, and cancelling it takes its preview off the screen."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from backend.tests.fake_clock import CLOCK
from desktop.native.widgets import LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free, qapp, settled  # noqa: F401


def test_running_late_says_where_each_block_goes_in_words(qapp: QApplication) -> None:  # noqa: F811
    dialog = LateDialog(None, "Starting from 16:00 today (Thursday).")
    trace = {
        "moves": [
            {"block_id": "essay", "from_start": "16:00", "to_start": "17:30"},
            {"block_id": "maths", "from_start": None, "to_start": "18:00"},
            {"block_id": "club", "from_start": "19:00", "to_start": None},
        ]
    }
    dialog.show_trace(trace, {"essay": "History essay", "maths": "Maths", "club": "Club"})
    rows = [dialog.changes.item(index).text() for index in range(dialog.changes.count())]
    assert rows == [
        "History essay: from 16:00 to 17:30",
        "Maths: placed at 18:00",
        "Club: moves off 19:00 and isn't placed",
    ]
    free(dialog)


def test_cancelling_running_late_takes_its_preview_off_the_screen(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = window.session
    thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=15, minutes=40)
    CLOCK.set(thursday)
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "estimate_min": 60,
            "revision": 0,
            "due": (thursday.date() + timedelta(days=2)).isoformat() + "T23:59",
        }
    )
    session.save()
    settled(qapp, window)
    # Running late moves only blocks that already have a time, so put the essay on Thursday at 16:00.
    essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    session.add_block({**essay, "start": "16:00", "days": [3]})
    session.save()
    settled(qapp, window)

    def run(dialog: LateDialog) -> int:
        dialog.show()
        dialog.preview_requested.emit()
        wait_until(qapp, lambda: session.late_preview is not None and not session.busy)
        assert window.toast.text() == "1 task moves"
        dialog.reject()
        return dialog.result()

    monkeypatch.setattr(LateDialog, "exec", run)
    window._open_late()
    qapp.processEvents()
    assert session.late_preview is None
    assert not window.toast.isVisible()
