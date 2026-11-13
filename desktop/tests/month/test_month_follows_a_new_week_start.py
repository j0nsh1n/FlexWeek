# ruff: noqa: F811
"""A new first day of the week shows at once on the screens already open: the Material month, the
Widgets month and Material Day's small month redraw without being left and opened again.

Dates come from the calendar. The clock is Thursday 5 November 2026; 1 November is a Sunday. November's
rows start on Sunday 1 November with a Sunday start and on Wednesday 28 October with a Wednesday start.
December's Wednesday rows start on Wednesday 25 November and its Sunday rows on Sunday 29 November, both
before the Monday rows' first date (30 November); homework due on such a date shows there.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native import fields  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import qml, visuals  # noqa: E402
from desktop.tests.month.support_material_month import (  # noqa: E402
    cell,
    open_month,
    seed_school_and_essay,
    shown_dates,
    texts,
)
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import settled  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-week-start"])


@pytest.fixture()
def window(qapp: QApplication, open_light: Callable[..., NativeWindow]) -> NativeWindow:
    made = open_light((1280, 800))
    seed_school_and_essay(made)
    return made


def _names(root) -> list[str]:
    return texts(qml(root, "materialMonth"), "monthWeekday")


@pytest.mark.parametrize(
    ("start", "first", "names"),
    (
        ("sunday", "2026-11-01", ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]),
        ("wednesday", "2026-10-28", ["Wed", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue"]),
    ),
)
def test_the_open_material_month_redraws_from_the_new_first_day(
    qapp: QApplication, window: NativeWindow, start: str, first: str, names: list[str]
) -> None:
    root, _month = open_month(qapp, window)
    assert _names(root)[0] == "Mon"
    assert shown_dates(root)[0] == "2026-10-26"
    fields.save_week_starts_on(start)
    wait_until(qapp, lambda: _names(root) == names, what="the weekday names to follow")
    wait_until(qapp, lambda: shown_dates(root)[0] == first, what="the rows to follow")
    assert date.fromisoformat(shown_dates(root)[-1]).weekday() == (fields.week_start_day() + 6) % 7


@pytest.mark.parametrize(
    ("start", "due", "first"),
    (("wednesday", "2026-11-26", "2026-11-25"), ("sunday", "2026-11-29", "2026-11-29")),
)
def test_december_shows_homework_due_before_its_monday_rows(
    qapp: QApplication, window: NativeWindow, start: str, due: str, first: str
) -> None:
    session = window.session
    session.add_homework(
        {"id": "lab", "title": "Lab report", "due": f"{due}T23:59", "estimate_min": 60, "revision": 0}
    )
    session.save()
    settled(qapp, window)
    fields.save_week_starts_on(start)
    root, _month = open_month(qapp, window)
    session.shift_month(1)
    wait_until(qapp, lambda: session.selected_month == "2026-12")
    wait_until(qapp, lambda: bool(shown_dates(root)) and shown_dates(root)[0] == first)
    wait_until(
        qapp,
        lambda: "Due Lab report" in texts(cell(root, due), "monthChipText"),
        what="the chip on the date before the Monday rows",
    )


def test_the_open_widgets_month_redraws_from_the_new_first_day(
    qapp: QApplication, window: NativeWindow
) -> None:
    window.session.set_view("month")
    wait_until(qapp, lambda: bool(window.month_grid.canvas.cells), what="the month to load")
    assert window.month_grid.canvas.cells[0].iso == "2026-10-26"
    fields.save_week_starts_on("wednesday")
    wait_until(
        qapp, lambda: window.month_grid.canvas.cells[0].iso == "2026-10-28", what="the rows to follow"
    )
    assert window.month_grid.scroll.names.names()[0] == "Wed"


def test_material_days_small_month_follows_a_new_first_day_at_once(
    qapp: QApplication, window: NativeWindow
) -> None:
    from desktop.tests.day.support_material_day import open_day_page

    root = open_day_page(qapp, window)
    mini = qml(root, "dayMiniMonth")

    def first_letter() -> str:
        return next(
            str(item.property("text")) for item in visuals(mini) if str(item.objectName()) == "letter0"
        )

    assert first_letter() == "M"
    fields.save_week_starts_on("sunday")
    wait_until(qapp, lambda: first_letter() == "S", what="the small month's letters to follow")
