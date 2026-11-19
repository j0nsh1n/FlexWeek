"""Lucide's icons: every icon the plan names ships with its licence, is drawn at the system's stroke, and
is sharp on a high-density screen; Replan and School have icons of their own. Whether
the School icon reads on its block is judged on the pictures in
pictures/screens_settings_h2.py.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native import calendar, icons
from desktop.native.calendar import CATEGORIES
from desktop.tests.window_support import qapp  # noqa: F401

# The plan's list, and what the mock-up's screens use on top of it.
PLANNED = (
    "settings",
    "chevron-left",
    "chevron-right",
    "chevron-down",
    "plus",
    "minus",
    "search",
    "book-open",
    "trash",
    "copy",
    "check",
    "eye",
    "eye-off",
    "clock",
    "calendar",
    "bell",
    "palette",
    "laptop",
    "timer",
    "log-out",
    "pin",
    "pencil",
    "undo-2",
    "x",
)


def test_every_icon_the_plan_names_ships_with_its_licence() -> None:
    assert set(PLANNED) <= set(icons.names())
    assert "ISC License" in (icons.ICON_DIR / "LICENSE.txt").read_text(encoding="utf-8")


def test_an_icon_is_drawn_at_the_systems_stroke() -> None:
    assert b'stroke-width="1.75"' in icons.svg("plus", "#111827")


def test_an_icon_is_sharp_on_a_high_density_screen(qapp: QApplication) -> None:  # noqa: F811
    drawn = icons.pixmap("clock", "#111827", 16, 2.0)
    assert (drawn.width(), drawn.height()) == (32, 32)
    assert drawn.devicePixelRatio() == 2.0




def test_school_is_the_school_building_everywhere_it_has_an_icon() -> None:
    """The block and the category were a house while School hours was a school building."""
    assert CATEGORIES["class"]["icon"] == "school"
    assert calendar.category_icon("class") == "school", "the engine draws the block with it"
    assert "school" in icons.names()


