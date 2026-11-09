"""Lucide's icons: every icon the plan names ships with its licence, is drawn at the system's stroke, and
is sharp on a high-density screen; Replan and School have icons of their own. Whether
the School icon reads on its block is judged on the pictures in
pictures/screens_settings_h2.py.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from desktop.native import calendar, icons
from desktop.native.calendar import CATEGORIES
from desktop.native.hours.canvas import BlockPainter, Drawn
from desktop.native.hours.geometry import Span
from desktop.native.look import category_paint, resolved_palette
from desktop.native.window import MORE_ICONS
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


def test_replan_has_its_own_icon_and_it_ships(qapp: QApplication) -> None:  # noqa: F811
    """Replan all my homework wore Activity's sparkles. Lucide's calendar-sync is its own."""
    assert "calendar-sync" in icons.names()
    assert MORE_ICONS["replanAll"] == "calendar-sync"
    taken = {name for key, name in MORE_ICONS.items() if key != "replanAll"}
    taken |= {info.get("icon") for info in CATEGORIES.values()}
    assert "calendar-sync" not in taken
    assert set(MORE_ICONS.values()) <= set(icons.names()), "every icon More names has a file"
    assert not icons.pixmap("calendar-sync", "#111827", 20).isNull(), "the SVG loads"
    assert b"<path" in icons.svg("calendar-sync", "#111827")
    assert b"currentColor" not in icons.svg("calendar-sync", "#111827")


def test_school_is_the_school_building_everywhere_it_has_an_icon() -> None:
    """The block and the category were a house while School hours was a school building."""
    assert CATEGORIES["class"]["icon"] == "school"
    assert calendar.category_icon("class") == "school", "the engine draws the block with it"
    assert "school" in icons.names()


@pytest.mark.parametrize(("pack", "dark"), [("light-frost", False), ("dark-frost", True)])
def test_the_school_block_draws_the_school_icon_and_its_edge_keeps_the_categorys_colour(
    qapp: QApplication,  # noqa: F811
    pack: str,
    dark: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    palette = resolved_palette(pack, dark, None)
    painter = BlockPainter(palette)
    drawn = Drawn("test", "School", "class", False, Span(0, 480, 660), 0, 1)
    fill, ink, _outline, edge = painter.fills(drawn)
    mark = category_paint("class", palette)[1]
    assert edge is None or edge.name() == mark, "the 3 px edge keeps the category's colour"

    used: list[str] = []
    original = icons.pixmap

    def record(name, colour, *args):
        used.append(name)
        return original(name, colour, *args)

    monkeypatch.setattr(icons, "pixmap", record)
    picture = QImage(500, 300, QImage.Format.Format_ARGB32)
    picture.fill(fill)
    paint = QPainter(picture)
    paint.setFont(QFont("Inter", 12))
    try:
        painter.words(paint, QRectF(0, 0, 480, 280), drawn, ink, QRectF(0, 0, 500, 300), fill, edge)
    finally:
        paint.end()
    assert "school" in used, used
