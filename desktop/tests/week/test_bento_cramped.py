"""Bento in a narrow window or with large text: the board sits in a scroll area, and the view says it is
cramped, which puts the tiles under the hero. (Where each tile lands is the picture week.bento_cramped.)"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.bento import BentoView  # noqa: E402
from desktop.native.layouts.registry import tokens_for  # noqa: E402
from desktop.native.look import PRESET_PALETTES  # noqa: E402
from desktop.native.weekmodel import WeekModel  # noqa: E402
from desktop.tests.day.support_bento import shown  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-cramped-test"])


@pytest.mark.parametrize(
    ("size", "scale", "cramped"),
    [
        ((800, 700), 1.0, True),
        ((1150, 768), 1.2, True),
        ((1024, 740), 1.0, True),
        ((1150, 768), 1.0, False),
        ((1280, 800), 1.0, False),
    ],
)
def test_a_narrow_window_or_large_text_makes_bento_cramped(
    qapp: QApplication, size: tuple[int, int], scale: float, cramped: bool
) -> None:
    view = shown(qapp, size=size, scale=scale)
    assert view.cramped is cramped
    view.close()


def test_the_board_sits_in_a_scroll_area_so_cards_below_the_window_can_be_reached(
    qapp: QApplication,
) -> None:
    """W4: at 1024 by 740 the cards below 740 px are reached by scrolling."""
    view = BentoView()
    view.resize(1024, 740)
    palette = PRESET_PALETTES["bento-indigo"]
    tokens = tokens_for("bento", "bento-indigo", palette)
    view.show_week(Scene(WeekModel("2026-10-12", ()), 5, 12 * 60, {}, tokens, 1.0))
    view.show()
    qapp.processEvents()
    scroll = view.findChild(QScrollArea, "bentoScroll")
    assert scroll is not None, "bentoScroll container is present"
    assert scroll.widget() is not None, "scroll area hosts the bento board"
    view.close()
