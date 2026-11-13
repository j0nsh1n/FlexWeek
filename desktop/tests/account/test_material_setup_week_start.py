"""Material setup's week page offers all seven days as the week's first day, in a drop-down list from
Monday to Sunday, and keeps the pick on this computer when the student moves on."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native import fields
from desktop.native.setup import HOMEWORK, WEEK
from desktop.tests.account.support import (
    LightLaunches,
    account,
    create,
    material_launches,  # noqa: F401
    named,
    root_of,
    through_recovery,
    visuals,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

SEVEN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def test_the_week_page_lists_every_day_and_keeps_a_wednesday_start(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "wednesday_student")
    through_recovery(qapp, window)
    bridge.setupNext()
    assert bridge.setupStep == WEEK
    wait_until(qapp, lambda: bool(named(window, "setupWeekStart")))
    choice = named(window, "setupWeekStart")[0]
    assert [row["label"] for row in choice.property("options").toVariant()] == SEVEN
    assert choice.property("accessName") == "Week starts on"
    assert choice.property("value") == "monday"
    assert [row["full"] for row in bridge.dayNames] == SEVEN
    # Week starts on the chosen day too, so the page no longer says it runs Monday to Sunday.
    said = [str(item.property("text") or "") for item in visuals(root_of(window))]
    assert "Week starts on" in " ".join(said)
    assert not [text for text in said if "Monday to Sunday" in text], said
    bridge.setWeekStart("wednesday")
    wait_until(qapp, lambda: choice.property("value") == "wednesday")
    # The day buttons follow the pick at once, and each still means its own weekday.
    assert [row["full"] for row in bridge.dayNames] == SEVEN[2:] + SEVEN[:2]
    saturday = named(window, "setupSchoolDay5")[0]
    assert saturday.property("on") is False
    bridge.toggleSchoolDay(5)
    wait_until(qapp, lambda: saturday.property("on") is True)
    bridge.toggleSchoolDay(5)
    assert fields.week_starts_on() == "monday"
    bridge.setupNext()
    assert bridge.setupStep == HOMEWORK
    assert fields.week_starts_on() == "wednesday"
