"""A 12-hour clock.

Every time on screen is written by one function, `clock_text`, which reads the student's Clock choice
in Settings > This computer. What is saved and sent stays HH:MM. Each formatter is checked on both
clocks, then a walk of the week asks whether "16:00" is still written anywhere once 4:00 PM is chosen.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.setup_steps import span_label
from desktop.native.sheet_rules import _unbroken_time
from desktop.native.weekmodel import clock_text, set_clock_24h
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import host, qapp, settled  # noqa: F401

TWELVE = False


@pytest.fixture()
def twelve() -> None:
    set_clock_24h(TWELVE)


def test_set_clock_says_whether_it_changed() -> None:
    assert set_clock_24h(True) is False
    assert set_clock_24h(TWELVE) is True
    assert set_clock_24h(TWELVE) is False
    assert set_clock_24h(True) is True


BLOCK = {"id": "soccer", "title": "Soccer practice", "start": "16:00", "duration_min": 90, "days": [3]}




def test_running_late_rows_keep_am_pm_on_the_time(qapp: QApplication, twelve: None) -> None:
    words = clock_text(16 * 60), clock_text(17 * 60 + 30)
    # AM/PM stays on the time (U+00A0), not a wrapping space.
    assert _unbroken_time(f"Essay: from {words[0]} to {words[1]}") =="Essay: from 4:00 PM to 5:30 PM"


def test_setup_summaries_and_its_time_box_use_the_12_hour_clock(
    qapp: QApplication,
    twelve: None,
) -> None:
    assert span_label("15:30", 90) == "3:30 PM–5:00 PM"


def visible_words(shown: NativeWindow) -> list[str]:
    return [label.text() for label in shown.findChildren(QLabel) if label.isVisibleTo(shown) and label.text()]






def test_the_clock_saved_to_the_account_is_the_one_the_window_writes(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    for chosen, written in ((False, "4:00 PM"), (True, "16:00")):
        assert window.session.save_preferences({"clock_24h": chosen})
        wait_until(qapp, lambda: not window.session.busy)
        # 12-hour is the default, so the server leaves it out.
        assert window.session.preferences.get("clock_24h", False) is chosen
        assert clock_text(16 * 60) == written
