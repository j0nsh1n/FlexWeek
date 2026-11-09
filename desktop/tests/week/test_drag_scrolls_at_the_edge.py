"""A held block scrolls the hours only when it rests at an edge, and at the same minutes a second at
any zoom. The hand reads its dwell from `hand_time`, which the test moves."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours import hand as hand_module  # noqa: E402
from desktop.tests.week.support_hand import Rig, hand_time, rig_of  # noqa: E402, F401
from desktop.tests.window_support import qapp  # noqa: E402, F401

TICK_S = 0.016


def hold_at_the_bottom_edge(rig: Rig) -> QPoint:
    """The hours taller than the window, scrolled to the top, a block held and carried to the bottom
    edge; returns that edge's point."""
    rig.window.resize(760, 500)
    QApplication.processEvents()
    rig.scroll.verticalScrollBar().setValue(0)
    bottom = rig.scroll.viewport().mapToGlobal(QPoint(150, rig.scroll.viewport().height() - 10))
    start = rig.at(1, 6 * 60 + 30)
    rig.send(rig.canvas, QEvent.Type.MouseButtonPress, start, True)
    rig.send(rig.canvas, QEvent.Type.MouseMove, start + QPoint(0, 40), True)
    rig.send(rig.canvas, QEvent.Type.MouseMove, bottom, True)
    return bottom


def test_passing_through_an_edge_does_not_scroll_but_resting_there_does(
    rig_of: Callable[..., Rig], hand_time: list[float]
) -> None:
    rig = rig_of(height=1632)
    bar = rig.scroll.verticalScrollBar()
    bottom = hold_at_the_bottom_edge(rig)
    # Through the edge on the way somewhere, briefer than the dwell, and out again.
    hand_time[0] += hand_module.DWELL_S / 3
    rig.hand._scroll_tick()
    rig.send(rig.canvas, QEvent.Type.MouseMove, bottom - QPoint(0, 80), True)
    hand_time[0] += 2 * hand_module.DWELL_S
    rig.hand._scroll_tick()
    assert bar.value() == 0, "passed through the edge: nothing moved"
    rig.send(rig.canvas, QEvent.Type.MouseMove, bottom, True)
    rig.hand._scroll_tick()
    assert bar.value() == 0, "only just arrived at the edge: nothing moved yet"
    hand_time[0] += hand_module.DWELL_S
    for _ in range(10):
        hand_time[0] += TICK_S
        rig.hand._scroll_tick()
    assert bar.value() > 0, "rested at the edge: it scrolls"
    rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, bottom, False)


def test_a_rested_edge_scrolls_the_same_minutes_a_second_at_any_zoom(
    rig_of: Callable[..., Rig], hand_time: list[float]
) -> None:
    seconds = 2.0
    rates = []
    for height in (1000, 2400):
        rig = rig_of(height=height)
        bar = rig.scroll.verticalScrollBar()
        bottom = hold_at_the_bottom_edge(rig)
        hand_time[0] += hand_module.DWELL_S
        for _ in range(round((seconds - hand_module.DWELL_S) / TICK_S)):
            hand_time[0] += TICK_S
            rig.hand._scroll_tick()
        rig.send(rig.canvas, QEvent.Type.MouseButtonRelease, bottom, False)
        per_minute = height / (rig.canvas.tracks[0].last - rig.canvas.tracks[0].first)
        rates.append(bar.value() / per_minute / (seconds - hand_module.DWELL_S))
    assert rates[0] == pytest.approx(rates[1], rel=0.05), f"minutes a second by zoom: {rates}"
    assert rates[0] == pytest.approx(hand_module.SCROLL_MINUTES_PER_S, rel=0.05)
