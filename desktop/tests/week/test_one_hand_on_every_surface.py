"""The contract between the one hand and whatever a design draws its hours on.

A test design here shows the week on every kind of surface at once: columns that run down, lanes
that run across, a card laid at an angle, a day cut into two tiles, and a dial. The same hand has to
land a block on each, keep it inside each tile's own hours, open a day from its name either way time
runs, and hold the design's renders from the moment of the press.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from desktop.native.hours.geometry import Span  # noqa: E402
from desktop.native.hours.hand import Create, Move, Place  # noqa: E402
from desktop.tests.week.support_hand import Stage, stage_of  # noqa: E402, F401
from desktop.tests.window_support import qapp  # noqa: E402, F401

HOURS = Path(__file__).resolve().parents[2] / "native" / "hours"


def test_one_hand_lands_a_block_on_every_kind_of_surface(stage_of: Callable[[], Stage]) -> None:
    stage = stage_of()
    view = stage.view
    for day, minute, surface in (
        (0, 10 * 60, view.down),
        (3, 10 * 60, view.across),
        (4, 10 * 60, view.card),
        (5, 7 * 60, view.morning),
        (5, 14 * 60, view.afternoon),
        (6, 9 * 60, view.dial),
    ):
        stage.place(day, minute, surface)
    starts = [(change.span.day, change.span.start) for change in stage.said]
    assert all(isinstance(change, Place) for change in stage.said)
    # Carried by the middle of nothing, a block's start is where it is let go, to the quarter hour.
    assert [(day, round(start / 15) * 15) for day, start in starts] == [
        (0, 600),
        (3, 600),
        (4, 600),
        (5, 420),
        (5, 840),
        (6, 540),
    ]


def test_a_design_lists_every_surface_it_shows(stage_of: Callable[[], Stage]) -> None:
    stage = stage_of()
    shown = stage.view.hours_surfaces()
    days = sorted({day for surface in shown for day in range(7) if surface.track_for(day) is not None})
    assert days == [0, 1, 2, 3, 4, 5, 6]
    assert len(shown) == 6


def test_a_tile_keeps_a_block_inside_its_own_hours(stage_of: Callable[[], Stage]) -> None:
    """The morning tile runs 06:00 to 12:00. A block carried to its end stops at noon; one resized
    past its end, or drawn past it, stops there too, whatever lies under the pointer."""
    stage = stage_of()
    tile, track = stage.view.morning, stage.view.morning.tracks[0]
    box = tile.block_rect("run", 5)
    grab = box.center()
    near_end = tile.mapToGlobal(track.point_for(11 * 60 + 50).toPoint())
    stage.send(tile, QEvent.Type.MouseButtonPress, grab, True)
    stage.carry(grab, near_end, tile)
    edge = QPoint(box.center().x(), box.bottom() - 2)
    below = stage.view.afternoon.mapToGlobal(stage.view.afternoon.tracks[0].point_for(15 * 60).toPoint())
    stage.send(tile, QEvent.Type.MouseButtonPress, edge, True)
    stage.carry(edge, below, tile)
    free = tile.mapToGlobal(track.point_for(10 * 60).toPoint()) + QPoint(0, 2)
    stage.send(tile, QEvent.Type.MouseButtonPress, free, True)
    stage.carry(free, below, tile)
    assert stage.said == [
        Move("run", 5, Span(5, 11 * 60, 12 * 60)),
        Move("run", 5, Span(5, 8 * 60, 12 * 60)),
        Create(Span(5, 10 * 60, 12 * 60)),
    ]


def test_a_click_near_a_tiles_end_makes_only_what_fits_in_it(stage_of: Callable[[], Stage]) -> None:
    stage = stage_of()
    tile, track = stage.view.morning, stage.view.morning.tracks[0]
    at = tile.mapToGlobal(track.point_for(11 * 60 + 30).toPoint()) + QPoint(0, 2)
    stage.send(tile, QEvent.Type.MouseButtonPress, at, True)
    stage.send(tile, QEvent.Type.MouseButtonRelease, at, False)
    assert stage.said == [Create(Span(5, 11 * 60 + 30, 12 * 60))]


def test_a_days_name_opens_it_whichever_way_its_time_runs(stage_of: Callable[[], Stage]) -> None:
    stage = stage_of()
    opened: list[int] = []
    for canvas in (stage.view.down, stage.view.across):
        canvas.day_opened.connect(opened.append)
    for day, canvas in (
        (0, stage.view.down),
        (1, stage.view.down),
        (2, stage.view.across),
        (3, stage.view.across),
    ):
        try:
            at = canvas.day_name(day)
        except LookupError as error:
            raise AssertionError(f"day {day} has no name to click: {error}") from None
        QTest.mouseClick(
            canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, canvas.mapFromGlobal(at)
        )
    assert opened == [0, 1, 2, 3]
    with pytest.raises(LookupError):
        stage.view.card.day_name(4)


def test_renders_are_held_from_the_press_until_the_hand_lets_go(stage_of: Callable[[], Stage]) -> None:
    """A tap holds them too: a rebuild between press and release would delete what was pressed."""
    stage = stage_of()
    held: list[bool] = []
    stage.hand.holding.connect(held.append)
    tile = stage.view.morning
    grab = tile.block_rect("run", 5).center()
    stage.send(tile, QEvent.Type.MouseButtonPress, grab, True)
    assert held == [True], "held before the pointer has moved at all"
    stage.send(tile, QEvent.Type.MouseButtonRelease, grab, False)
    stage.send(tile, QEvent.Type.MouseButtonPress, grab, True)
    QTest.keyClick(tile, Qt.Key.Key_Escape)
    stage.send(tile, QEvent.Type.MouseButtonPress, grab, True)
    stage.hand.cancel()
    assert held == [True, False, True, False, True, False]


def test_the_shared_hours_have_one_set_of_drag_rules() -> None:
    """Only the hand decides when a press becomes a drag, only geometry snaps, and nothing in the
    shared hours uses Qt's system drag and drop."""
    sources = {path.name: path.read_text() for path in HOURS.glob("*.py")}
    assert not [name for name, text in sources.items() if re.search(r"\bQDrag\b|\bQMimeData\b", text)]
    assert [name for name, text in sources.items() if "startDragDistance" in text] == ["hand.py"]
    assert [name for name, text in sources.items() if re.search(r"^def snap\b", text, re.M)] == [
        "geometry.py"
    ]


def test_nothing_in_the_app_uses_system_drag_and_drop() -> None:
    """Every block moves through the one hand. Qt's system drag and drop is where Wayland and X11
    differ and where the rig cannot see what the student sees, so nothing may take it up again."""
    app = HOURS.parent
    system_drag = r"\bQDrag\b|\bQMimeData\b|\bsetAcceptDrops\b|\bdropEvent\b"
    found = [
        f"{path.relative_to(app)}: {match.group()}"
        for path in sorted(app.rglob("*.py"))
        for match in re.finditer(system_drag, path.read_text())
    ]
    assert found == []
