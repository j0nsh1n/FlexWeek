"""The small calendars start their rows on the day the week starts on, dates and letters both: the
Material small month (Day's side month and the date picker), the Widgets Day rail's month and the
study-hours strip.

Dates come from the calendar: 1 November 2026 is a Sunday, so with a Wednesday start November's rows
open on Wednesday 28 October and the 1st sits in the fifth column; with a Monday start it is the
seventh column, with a Saturday start the second. The shared fake clock is Thursday 5 November 2026.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import json
from datetime import date

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native import fields  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import open_day_page  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402,F401
from desktop.tests.material_support import qml, visuals  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402,F401

LETTERS = {
    "monday": ["M", "T", "W", "T", "F", "S", "S"],
    "wednesday": ["W", "T", "F", "S", "S", "M", "T"],
    "saturday": ["S", "S", "M", "T", "W", "T", "F"],
    "sunday": ["S", "M", "T", "W", "T", "F", "S"],
}
# Where 1 November 2026 (a Sunday) sits in its row, and the first and last dates of November's rows.
NOVEMBER = {
    "monday": (6, date(2026, 10, 26), date(2026, 12, 6)),
    "wednesday": (4, date(2026, 10, 28), date(2026, 12, 1)),
    "saturday": (1, date(2026, 10, 31), date(2026, 12, 4)),
    "sunday": (0, date(2026, 11, 1), date(2026, 12, 5)),
}


def _start_on(start: str) -> None:
    """The per-computer file as a pick writes it, written here so an app that cannot read the day
    shows its own Monday rather than refusing the test."""
    path = fields._week_starts_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"week_starts_on": start}), encoding="utf-8")


def _texts_by_name(mini: QObject, prefix: str) -> dict[str, str]:
    return {
        str(item.objectName()): str(item.property("text"))
        for item in visuals(mini)
        if str(item.objectName()).startswith(prefix)
    }


@pytest.mark.parametrize("start", ["wednesday", "monday", "saturday"])
def test_material_days_small_month_starts_its_rows_on_the_chosen_day(
    qapp: QApplication, window: NativeWindow, start: str
) -> None:
    _start_on(start)
    root = open_day_page(qapp, window)
    mini = qml(root, "dayMiniMonth")
    letters = _texts_by_name(mini, "letter")
    assert [letters[f"letter{at}"] for at in range(7)] == LETTERS[start]
    cells = _texts_by_name(mini, "cell")
    column, first, _last = NOVEMBER[start]
    assert cells[f"cell{column}"] == "1"
    assert cells["cell0"] == str(first.day)


@pytest.mark.parametrize("start", ["wednesday", "monday", "saturday", "sunday"])
def test_the_widgets_day_rails_month_starts_its_rows_on_the_chosen_day(
    qapp: QApplication, start: str
) -> None:
    from desktop.native.hours.rail import MiniMonth

    _start_on(start)
    month = MiniMonth()
    month.month = date(2026, 11, 1)
    shown = month.dates()
    column, first, last = NOVEMBER[start]
    assert shown[0] == first
    assert shown[-1] == last
    assert shown[column] == date(2026, 11, 1)
    assert len(shown) % 7 == 0
    assert list(month.letters()) == LETTERS[start]
    month.deleteLater()


@pytest.mark.parametrize("start", ["wednesday", "monday", "sunday"])
def test_the_study_hours_strip_runs_from_the_chosen_day(qapp: QApplication, start: str) -> None:
    from desktop.native.widgets import AvailabilityStrip

    _start_on(start)
    strip = AvailabilityStrip({"muted": "#666", "hairline": "#ddd", "accent": "#36c", "error": "#c00"})
    order = {
        "monday": [0, 1, 2, 3, 4, 5, 6],
        "wednesday": [2, 3, 4, 5, 6, 0, 1],
        "sunday": [6, 0, 1, 2, 3, 4, 5],
    }
    assert strip.days() == order[start]
    assert strip.letters() == LETTERS[start]
    strip.deleteLater()
