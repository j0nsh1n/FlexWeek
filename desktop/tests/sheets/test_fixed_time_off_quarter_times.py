# ruff: noqa: F811
"""Edit fixed time for a block that is not on a quarter hour (the plain look's 5-minute drag makes them):
Start and End show the block's own times, Save without touching them keeps them, and Up and Down step to
the next time in time order, never to midnight.

Expected values come from the block seeded here: Club, Friday 16:55 for 90 minutes, so it ends at 18:25.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    find_named,
    open_light,
    qapp,
    settle,
    sheets,
    shell,
)

FRIDAY = 4
START = 16 * 60 + 55
END = START + 90


def _clock_style(shell: NativeWindow, hour24: bool) -> None:
    """The clock style is the account's setting; the window reads it into the one app-wide clock."""
    shell.session.preferences = {**(shell.session.preferences or {}), "clock_24h": hour24}
    shell._set_clock()


def _seed_club(qapp: QApplication, shell: NativeWindow) -> None:
    shell.session.add_block(
        {
            "id": "club",
            "title": "Club",
            "kind": "locked",
            "category": "extra",
            "start": "16:55",
            "duration_min": 90,
            "days": [FRIDAY],
        }
    )
    shell.session.save()
    settle(qapp, shell)


def _open_club(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _seed_club(qapp, shell)
    sheets.editBlock("club", FRIDAY)
    pump(qapp)
    assert sheets.kind == "block"


def _labels(options: list[dict]) -> list[str]:
    return [item["label"] for item in options]


def _in_time_order(options: list[dict], minutes) -> bool:
    values = [minutes(item["value"]) for item in options]
    return values == sorted(set(values))


def test_start_and_end_list_the_blocks_own_times_in_the_24_hour_clock(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _clock_style(shell, True)
    _open_club(qapp, shell, sheets)
    form = sheets.form
    start_labels, end_labels = _labels(form["startOptions"]), _labels(form["endOptions"])
    assert start_labels.count("16:55") == 1
    assert end_labels.count("18:25") == 1
    assert [item["label"] for item in form["startOptions"] if item["value"] == form["start"]] == ["16:55"]
    assert [item["label"] for item in form["endOptions"] if item["value"] == form["end"]] == ["18:25"]
    assert _in_time_order(form["startOptions"], lambda v: int(v[:2]) * 60 + int(v[3:]))
    assert _in_time_order(form["endOptions"], int)


def test_the_off_quarter_times_read_in_the_12_hour_clock_when_that_is_the_account_clock(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _clock_style(shell, False)
    _open_club(qapp, shell, sheets)
    form = sheets.form
    assert _labels(form["startOptions"]).count("4:55 PM") == 1
    assert _labels(form["endOptions"]).count("6:25 PM") == 1


def test_the_field_shows_the_blocks_own_start_and_end(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _clock_style(shell, True)
    _open_club(qapp, shell, sheets)
    root = shell._material_page._quick.rootObject()
    assert find_named(root, "blockStart").property("shown") == "16:55"
    assert find_named(root, "blockEnd").property("shown") == "18:25"


def test_save_without_touching_the_times_keeps_them_exactly(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_club(qapp, shell, sheets)
    sheets.setText("title", "Club night")
    sheets.save()
    pump(qapp)
    settle(qapp, shell)
    saved = next(item for item in shell.session.blocks if item["id"] == "club")
    assert saved["title"] == "Club night"
    assert saved["start"] == "16:55"
    assert saved["duration_min"] == 90


def _press_on(qapp: QApplication, shell: NativeWindow, field_name: str, key) -> None:
    root = shell._material_page._quick.rootObject()
    find_named(root, field_name).forceActiveFocus()
    pump(qapp)
    QTest.keyClick(shell._material_page._quick, key)
    pump(qapp, 8)


def test_down_and_up_on_start_step_to_the_neighbours_in_time_order_never_to_midnight(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    _open_club(qapp, shell, sheets)
    _press_on(qapp, shell, "blockStart", Qt.Key.Key_Down)
    assert sheets.form["start"] == "17:00", "Down from 16:55 is the next time in order"
    _press_on(qapp, shell, "blockStart", Qt.Key.Key_Up)
    assert sheets.form["start"] == "16:55", "the block's own time stays on offer after Start moved off it"
    sheets.forceClose()
    pump(qapp, 5)


def test_down_on_end_goes_to_the_next_time_in_order(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    _open_club(qapp, shell, sheets)
    _press_on(qapp, shell, "blockEnd", Qt.Key.Key_Down)
    assert sheets.form["end"] == 18 * 60 + 30
    sheets.forceClose()
    pump(qapp, 5)


def test_a_quarter_hour_block_lists_no_extra_times(qapp: QApplication, shell: NativeWindow, sheets) -> None:
    sheets.editBlock("school", 0)
    pump(qapp)
    form = sheets.form
    assert len(form["startOptions"]) == 24 * 4
    assert len(form["endOptions"]) == 24 * 4
