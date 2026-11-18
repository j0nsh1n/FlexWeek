# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
"""Setup's rules on their own: a typed sport name is sports, and a time box steps a quarter hour while
a typed time keeps its minute."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QApplication, QDateTimeEdit

from desktop.native.fields import QuarterTime
from desktop.native.setup_steps import activity_category_for
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_typed_sport_name_is_sports(qapp: QApplication) -> None:
    assert activity_category_for("Soccer") == "exercise"
    assert activity_category_for("swim practice") == "exercise"
    assert activity_category_for("Piano practice") == "extra"
    assert activity_category_for("Band practice") == "extra"
    assert activity_category_for("Band") == "extra"


def test_a_time_steps_a_quarter_hour_and_a_typed_one_keeps_its_minute(qapp: QApplication) -> None:
    """School that starts at 08:05 starts at 08:05. It was moved to 08:00 without a word."""
    field = QuarterTime("08:00")
    field.setCurrentSection(QDateTimeEdit.Section.MinuteSection)
    field.stepBy(1)
    assert field.hhmm() == "08:15"
    field.stepBy(-2)
    assert field.hhmm() == "07:45"
    field.setTime(QTime(8, 7))
    field.editingFinished.emit()
    assert field.hhmm() == "08:07"
    field.stepBy(1)
    assert field.hhmm() == "08:15", "the arrows go on to the quarter hour either side"
    field.setTime(QTime(8, 7))
    field.stepBy(-1)
    assert field.hhmm() == "08:00"
