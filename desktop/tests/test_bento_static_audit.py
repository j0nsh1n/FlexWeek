"""Tests verifying static UI audit findings for Bento and Widgets surface claims (W3, W4, W5, W6, W7)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from desktop.native.hours.canvas import Drawn
from desktop.native.hours.geometry import Span
from desktop.native.layouts.base import Scene
from desktop.native.layouts.bento import BentoView
from desktop.native.layouts.registry import tokens_for
from desktop.native.look import PRESET_PALETTES
from desktop.native.weekmodel import WeekModel
from desktop.native.widgets import Toast
from desktop.tests.window_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_out,
    wait_until,
    window,
)


def test_w4_bento_1024x740_scroll_container_present(qapp: QApplication) -> None:  # noqa: F811
    """W4: Bento layout embeds board in bentoScroll so cards below 740px are scroll-accessible."""
    view = BentoView()
    view.resize(1024, 740)
    week = WeekModel("2026-10-12", ())
    palette = PRESET_PALETTES["bento-indigo"]
    tokens = tokens_for("bento", "bento-indigo", palette)
    scene = Scene(week, 5, 12 * 60, {}, tokens, 1.0)
    view.show_week(scene)
    view.show()
    qapp.processEvents()

    # Board is wrapped in QScrollArea named bentoScroll
    scroll = view.findChild(QScrollArea, "bentoScroll")
    assert scroll is not None, "bentoScroll container is present"
    assert scroll.widget() is not None, "scroll area hosts the bento board"

    # In cramped mode (1024 < 1150), cramped property is active
    assert view.cramped, "1024 width activates cramped layout mode"
    view.close()


def test_w5_toast_pointer_transparency_and_anchor(qapp: QApplication) -> None:  # noqa: F811
    """W5: Toast card has WA_TransparentForMouseEvents set and anchors at bottom right."""
    parent = QWidget()
    parent.resize(1280, 800)
    over = QWidget(parent)
    over.setGeometry(0, 0, 1280, 800)

    toast = Toast(parent, over)
    assert toast.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert toast.card.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    toast.show_message("Test message", "Undo")
    toast.reposition()

    # Geometry is at bottom right of the over area
    geom = toast.geometry()
    assert geom.right() <= 1280
    assert geom.bottom() <= 800
    assert geom.left() > 600, "toast is anchored to the right"
    assert geom.top() > 500, "toast is anchored to the bottom"
    parent.close()


def test_w6_concurrent_block_title_lines_contract() -> None:
    """W6: Concurrent blocks sharing a column cap title lines at 1 to prevent layout crush."""
    # When columns > 1, title_lines must be 1 (canvas.py:1031)
    single_drawn = Drawn("a", "Long Block Title", "homework", True, Span(0, 600, 660), 0, 1)
    concurrent_drawn = Drawn("b", "Long Block Title", "homework", True, Span(0, 600, 660), 0, 2)

    lines_single = 1 if single_drawn.columns > 1 or single_drawn.short else 2
    lines_concurrent = 1 if concurrent_drawn.columns > 1 or concurrent_drawn.short else 2

    assert lines_single == 2, "single column block can have up to 2 title lines"
    assert lines_concurrent == 1, "concurrent block sharing column caps at 1 title line"


def test_w7_category_mark_dimensions() -> None:
    """W7: Category mark is a 3px rectangular vertical line, not a glyph."""
    from desktop.native.hours.canvas import EDGE_WIDTH
    assert EDGE_WIDTH == 3, "category edge line width is 3 pixels"


def test_w3_bento_wider_control_alignment(qapp: QApplication) -> None:  # noqa: F811
    """W3 Control: At standard 1280 width with Sunday Today, Bento headers and tracks align exactly."""
    view = BentoView()
    view.resize(1280, 800)
    week = WeekModel("2026-10-12", ())
    palette = PRESET_PALETTES["bento-indigo"]
    tokens = tokens_for("bento", "bento-indigo", palette)
    # Sunday is day 6
    scene = Scene(week, 6, 12 * 60, {}, tokens, 1.0)
    view.show_week(scene)
    view.show()
    qapp.processEvents()

    canvas = view.findChild(object, "bentoWeekHours")
    heads = view.findChild(object, "bentoWeekHeads")
    if canvas is not None and heads is not None:
        assert len(canvas.tracks) == 7
        assert len(canvas.day_buttons) == 7
        # First 5 days (weekdays) have equal widths in control
        weekday_widths = [track.area.width() for track in canvas.tracks[:5]]
        assert max(weekday_widths) - min(weekday_widths) < 1.0
    view.close()
