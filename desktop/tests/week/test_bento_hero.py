"""Bento's hero is a choice between the week and today, and an older saved Bento still opens as it was."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours.chips import TrayChip  # noqa: E402
from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.bento import BentoView  # noqa: E402
from desktop.native.layouts.registry import LAYOUTS, options_for, tokens_for  # noqa: E402
from desktop.native.look import design_look  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.tests.day.support_bento import hours  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-hero-test"])


def test_the_hero_is_a_choice_of_week_or_today_and_the_week_comes_first() -> None:
    hero = next(option for option in LAYOUTS["bento"].options if option.key == "hero")
    assert (hero.label, hero.level) == ("Hero", "style")
    assert [(choice.value, choice.label) for choice in hero.choices] == [("week", "Week"), ("today", "Today")]
    assert options_for(None, "bento")["hero"] == "week"


def test_a_bento_saved_before_the_hero_still_opens_as_it_was(qapp: QApplication) -> None:
    """0.16 saved Supporting tiles too; that option went, and what else was saved is kept."""
    saved = {"main": "bento", "options": {"bento": {"colour": "sunset", "corners": "square",
                                                    "tiles": "essentials"}}}
    assert options_for(saved, "bento") == {
        "look": "preset:poster", "hero": "week", "corners": "square"
    }
    view = BentoView()
    view.resize(1150, 768)
    options = options_for(saved, "bento")
    week = build_week(WEEK, BLOCKS, HOMEWORK, TRACE)
    applied, _ = design_look(options["look"], "light-frost", False, None)
    view.show_week(Scene(week, 3, minute_of("13:40"), options, tokens_for("bento", options["look"], applied)))
    view.show()
    qapp.processEvents()
    assert hours(view, "bentoWeekHours").isVisible()
    assert view.findChild(TrayChip, "bentoWaiting0").isVisible()
