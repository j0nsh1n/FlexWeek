# ruff: noqa: F811
"""Every Widgets design that draws a Week names each day from its date, so a week from Wednesday
reads Wednesday 4 to Tuesday 10 November 2026 (the clock is Thursday 5 November). A day name beside a
date of another weekday is the bug this catches."""

from __future__ import annotations

import re
from datetime import date

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget  # noqa: E402

from desktop.native import fields  # noqa: E402
from desktop.native.layouts.registry import layouts_for  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import qapp, window  # noqa: E402, F401
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import settled  # noqa: E402

NAMED_DATE = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,? (\d{1,2})\b(?![:.]\d)(?! ?h\b)(?! ?min)")
SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _said(window: NativeWindow) -> list[str]:
    """Everything the Widgets week says: label and button words, accessible names and tooltips."""
    found: list[str] = []
    for widget in window.findChildren(QWidget):
        if not widget.isVisible():
            continue
        if isinstance(widget, (QLabel, QAbstractButton)):
            found.append(widget.text())
        found.extend((widget.accessibleName(), widget.toolTip()))
    return [text for text in found if text]


def _misnamed(texts: list[str]) -> list[str]:
    """Words that put a weekday next to a November 2026 date that is not that weekday."""
    wrong = []
    for text in texts:
        for match in NAMED_DATE.finditer(text):
            number = int(match.group(2))
            if not 1 <= number <= 30:
                continue
            if SHORT[date(2026, 11, number).weekday()] != match.group(1):
                wrong.append(text)
    return wrong


@pytest.mark.parametrize("design", [spec.id for spec in layouts_for("plan")])
def test_every_widgets_week_names_each_day_from_its_date(qapp, window, design: str) -> None:
    window._layout = {"main": design, "day": "one", "options": {}}
    window.session.set_view("week")
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: window.session.week_start == "2026-11-04" and not window.session.busy)
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    said = _said(window)
    # Some designs put the name and the date in labels of their own, side by side.
    together = " ".join(said)
    assert re.search(r"\bWed(nesday)?,? 4\b", together), together
    assert _misnamed([*said, together]) == []


def test_the_rail_month_bands_the_week_on_screen_from_its_first_day(qapp, window) -> None:
    window._layout = {"main": "classic", "day": "one", "options": {}}
    window.session.set_view("week")
    fields.save_week_starts_on("wednesday")
    wait_until(qapp, lambda: window.session.week_start == "2026-11-04" and not window.session.busy)
    settled(qapp, window)
    window._on_week()
    qapp.processEvents()
    month = window.rail.month.dates
    assert month.accessibleDescription() == "Shows the week of Wed 4 Nov."
    # The band goes on the row that starts on the week's first day.
    rows = [month.dates()[at] for at in range(0, len(month.dates()), 7)]
    assert date(2026, 11, 4) in rows
