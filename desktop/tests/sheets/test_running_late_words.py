"""Running late says where each block goes in words."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.widgets import LateDialog
from desktop.tests.light_app import window  # noqa: F401
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
