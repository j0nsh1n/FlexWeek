"""Setup's rail of steps: a finished step shows a tick, a skipped one a dash, the current one a ring."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from desktop.native.look import pack_stylesheet, resolved_palette, sanitize_look
from desktop.native.setup import (
    BADGE_PX,
    CURRENT,
    FINISHED,
    HOMEWORK,
    PENDING,
    SKIPPED,
    SetupPage,
    step_badge,
)
from desktop.native.tokens import contrast
from desktop.native.widgets import control_art
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.window_support import qapp  # noqa: F401


def picture(setup: SetupPage, index: int) -> object:
    return setup.rail_items[index].icon().pixmap(QSize(BADGE_PX, BADGE_PX)).toImage()


def badge(number: int, state: str, setup: SetupPage) -> object:
    family = setup.rail_items[0].font().family()
    drawn: QPixmap = step_badge(number, state, setup._palette, family)
    return drawn.toImage()


def test_a_finished_step_shows_a_tick_on_the_rail(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    setup = show_setup(qapp, window)
    setup.next.click()
    setup.next.click()
    assert setup.step == HOMEWORK
    states = [FINISHED, FINISHED, CURRENT, PENDING, PENDING, PENDING]
    for index, state in enumerate(states):
        assert picture(setup, index) == badge(index + 1, state, setup), (index, state)
    assert [item.accessibleDescription() for item in setup.rail_items[:3]] == ["Done", "Done", "Current step"]
    assert badge(1, PENDING, setup) != badge(1, FINISHED, setup)


def test_a_skipped_step_is_marked_skipped_not_done(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    """A step left by Skip is not done, so it shows a dash in a dashed ring, not the tick."""
    setup = show_setup(qapp, window)
    setup.skip.click()
    setup.skip.click()
    assert setup.step == HOMEWORK
    states = [SKIPPED, SKIPPED, CURRENT, PENDING, PENDING, PENDING]
    for index, state in enumerate(states):
        assert picture(setup, index) == badge(index + 1, state, setup), (index, state)
    assert [item.accessibleDescription() for item in setup.rail_items[:3]] == [
        "Skipped",
        "Skipped",
        "Current step",
    ]
    assert badge(1, SKIPPED, setup) != badge(1, FINISHED, setup)


@pytest.mark.parametrize("pack", ["light-frost", "dark-frost", "nocturne", "slate"])
@pytest.mark.parametrize(
    "preset", ["default", "high-contrast", "paper", "ink", "poster", "terminal", "pastel"]
)
def test_a_future_step_on_the_rail_reads_at_4_5_to_1(qapp: QApplication, pack: str, preset: str) -> None:
    """A step you cannot reach yet is drawn in the rail's disabled colour, which was a 2.3 to 1 grey on
    the white rail, below what text needs. The colour is read from the stylesheet, not from a picture."""
    look = sanitize_look({"preset": preset, "knobs": {}})
    palette = resolved_palette(pack, False, look)
    sheet = pack_stylesheet(pack, False, look, "default", palette, control_art(palette))
    rule = re.search(r"QPushButton#setupRailItem:disabled \{[^}]*color: (#[0-9a-fA-F]{6});", sheet)
    assert rule is not None
    assert contrast(rule.group(1), palette["panel"]) >= 4.5, (rule.group(1), palette["panel"])
