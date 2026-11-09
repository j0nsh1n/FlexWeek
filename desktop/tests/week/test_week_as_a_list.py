"""The week read as a list: its one name, its shortcut in Help, and each block's title in it."""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.calendar import DAY_FULL
from desktop.native.hours.canvas import HoursCanvas
from desktop.native.settings import HELP_KEYS
from desktop.native.weekmodel import length_label, range_label
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.week.support_material import seeded
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_week_list_has_one_name_and_its_shortcut_is_in_help(qapp, window) -> None:
    seeded(qapp, window)
    listed = window.week_access_list
    assert listed.accessibleName() == "Week as a list"
    assert listed.accessibleDescription() == (
        "Every block this week, day by day, in time order. Press Enter to open one."
    )
    window._sync_more_menu()
    names = [action.text() for action, button in window._more_pairs if button.objectName() == "weekListRow"]
    assert names == ["Week as a list"]
    hint = "Press Ctrl+Shift+L for the week as a list."
    (week_view,) = [canvas for canvas in window.findChildren(HoursCanvas) if canvas.isVisible()]
    assert week_view.accessibleDescription().endswith(hint)
    assert ("[Ctrl]+[Shift]+[L]", "Week as a list") in HELP_KEYS


def test_the_week_list_keeps_each_blocks_title(qapp, window) -> None:
    """A dropped on-block title stays in the week list; the hours keep their own name."""
    seeded(qapp, window)
    listed = [window.week_access_list.item(i).text() for i in range(window.week_access_list.count())]
    soccer = (
        f"{DAY_FULL[3]}: Soccer practice, {range_label(16 * 60, 17 * 60 + 30)} · "
        f"{length_label(90)} · Fixed time"
    )
    essay = f"{DAY_FULL[3]}: History essay, {range_label(19 * 60, 20 * 60)} · {length_label(60)} · Pinned"
    assert soccer in listed
    assert essay in listed
    (week_view,) = [canvas for canvas in window.findChildren(HoursCanvas) if canvas.isVisible()]
    assert week_view.accessibleName() == "Week view, hours"
