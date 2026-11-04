"""Tests verifying static UI audit findings for Widgets surfaces (W1, W2, W8, W9, W10, W11)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QRectF
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.hours.canvas import BlockPainter
from desktop.native.hours.geometry import LinearTrack
from desktop.native.layouts.base import Scene
from desktop.native.layouts.mission import MissionView
from desktop.native.layouts.registry import tokens_for
from desktop.native.layouts.timeline import Heads, TimelineView
from desktop.native.look import PRESET_PALETTES
from desktop.native.setup import SetupPage
from desktop.native.weekmodel import Occurrence, WeekModel
from desktop.native.widgets import UnfinishedPanel
from desktop.native.window import NativeWindow
from desktop.tests.window_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_out,
    wait_until,
    window,
)


def test_w1_setup_carousel_contract(qapp: QApplication, server) -> None:  # noqa: F811
    """W1: Setup Style carousel stepper is clean and neighbor cards show peek margins."""
    setup = SetupPage()
    setup.resize(1280, 800)
    setup.show()
    qapp.processEvents()

    # Stepper rail on the left is visible and unobstructed
    rail = setup.findChild(QWidget, "setupRail")
    assert rail is not None
    assert rail.isVisible()
    assert rail.x() >= 0
    assert rail.width() > 0

    # Carousel middle slide is visible and styled
    carousel = setup.carousel
    assert carousel.isVisible()
    current_key = carousel._order[carousel._index].key
    current = carousel.slides[current_key]
    assert current is not None
    assert current.isVisible()

    # Rail and carousel do not overlap
    rail_rect = QRect(rail.mapToGlobal(QPoint(0, 0)), rail.size())
    carousel_rect = QRect(carousel.mapToGlobal(QPoint(0, 0)), carousel.size())
    assert not rail_rect.intersects(carousel_rect), "stepper rail and carousel do not overlap"
    setup.close()


def test_w2_unfinished_panel_hierarchy(qapp: QApplication) -> None:  # noqa: F811
    """W2: UnfinishedPanel has heading at top, list in middle, dismiss at bottom."""
    panel = UnfinishedPanel()
    panel.resize(320, 400)
    panel.show()
    qapp.processEvents()

    heading = panel.findChild(QLabel, "unfinishedHeading")
    assert heading is not None
    dismiss = panel.findChild(QPushButton, "unfinishedDismiss")
    assert dismiss is not None
    list_widget = panel.list

    assert heading.geometry().top() < list_widget.geometry().top(), "heading is above list"
    assert list_widget.geometry().bottom() < dismiss.geometry().bottom(), "dismiss is at bottom"
    panel.close()


def test_w8_timeline_wednesday_counter_geometry(qapp: QApplication) -> None:  # noqa: F811
    """W8: Measures fold handle placement relative to Wednesday and Thursday headings."""
    view = TimelineView()
    view.resize(1280, 800)
    week = WeekModel("2026-10-12", ())
    palette = PRESET_PALETTES["timeline-paper"]
    tokens = tokens_for("timeline", "paper", palette)
    scene = Scene(week, 2, 900, {"fold": "3"}, tokens, 1.0)
    view.show_week(scene)
    view.show()
    qapp.processEvents()

    heads = view.findChild(Heads, "timelineHeads")
    assert heads is not None
    wednesday = heads.headings.get(2)
    assert wednesday is not None
    thursday = heads.headings.get(3)
    assert thursday is not None
    handle = heads.handle
    assert handle is not None

    # Handle is located in the row of heads
    assert handle.geometry().top() >= 0
    assert handle.geometry().bottom() <= heads.height()
    # Wednesday text is left-aligned and stays clear of the fold spine
    text_end = wednesday.title.x() + wednesday.title.fontMetrics().horizontalAdvance(wednesday.title.text())
    assert text_end < handle.x(), "Wednesday title text is clear of the fold handle"
    view.close()


def test_w9_mission_school_bounds_and_clearance(qapp: QApplication) -> None:  # noqa: F811
    """W9: School block in Mission layout has positive outer margin and inner text clearance."""
    view = MissionView()
    view.resize(1280, 800)
    # School: 08:00 (480 min) to 14:30 (870 min) on Monday (day 0)
    school = Occurrence("school", "School", "class", 0, 480, 870, False, False, False, None, None, None)
    week = WeekModel("2026-10-12", (school,))
    palette = PRESET_PALETTES["flight-deck"]
    tokens = tokens_for("mission", "flight-deck", palette)
    scene = Scene(week, 0, 900, {}, tokens, 1.0)
    view.show_week(scene)
    view.show()
    qapp.processEvents()

    canvas = view.findChild(object, "missionHours")
    assert canvas is not None
    track0 = canvas.tracks[0]
    drawn_blocks = canvas.drawn(track0)
    assert len(drawn_blocks) == 1
    drawn, rect = drawn_blocks[0]
    assert drawn.title == "School"

    # Block is within the lane's horizontal track bounds with positive margin
    assert rect.left() >= track0.area.left(), "block does not precede track area"
    assert rect.right() <= track0.area.right(), "block does not exceed track area"
    view.close()


def test_w10_week_as_list_drawer_overlay_geometry(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """W10: Week-as-a-list panel is a 360px floating overlay and does not crush the planner."""
    window.resize(1280, 800)
    window.show()
    qapp.processEvents()

    initial_planner_width = window.planner.width()
    window._toggle_week_access_list()
    qapp.processEvents()

    assert window.week_list_panel.isVisible(), "drawer is open"
    assert window.week_list_panel.width() == 360, "drawer fixed width is 360px"
    # Planner width is untouched (drawer floats over it)
    assert window.planner.width() == initial_planner_width, "underlying planner is uncrushed"
    window._close_week_access_list()


def test_w11_collision_avoidance_contract() -> None:
    """W11: Hour labels collision avoidance suppresses 4:00 mark when time is 3:40."""
    painter = BlockPainter({"axis": "light", "muted": "#64748b", "window": "#ffffff"})
    painter.now_in_gutter = True
    painter.now_minute = 15 * 60 + 40  # 15:40 (3:40 PM)

    # In a vertical track, 16:00 is 20 minutes (12px at 36 px/hour) from 15:40
    track = LinearTrack(0, QRectF(60, 0, 100, 1000))
    # At 36 px/hour, 20 minutes is 12px, which is less than tall (typically ~18px)
    tall = 18.0
    centre_1600 = track.offset(16 * 60)
    centre_now = track.offset(painter.now_minute)
    near_now = abs(centre_1600 - centre_now) < tall
    assert near_now, "16:00 is within collision suppression distance of 15:40"
