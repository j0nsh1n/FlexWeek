"""Setup's Week page: what its note and its school hint say, and when."""

# ruff: noqa: F811  (a test's fixture parameter has the name of the imported fixture)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from desktop.native.setup import WEEK
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.setup.support_setup_page import show_setup
from desktop.tests.window_support import qapp  # noqa: F401


def test_the_school_hint_shows_only_when_no_school_day_is_picked(
    qapp: QApplication,
    window: NativeWindow,
) -> None:
    setup = show_setup(qapp, window, WEEK)
    assert not setup.school_hint.isVisibleTo(setup), "under a week of school days it read as a warning"
    setup.school_days.set_days([])
    assert setup.school_hint.isVisibleTo(setup)
    setup.school_days.set_days([2])
    assert not setup.school_hint.isVisibleTo(setup)


def test_the_week_note_has_a_subject(qapp: QApplication, window: NativeWindow) -> None:
    setup = show_setup(qapp, window, WEEK)
    note = setup.pages[WEEK].findChild(QLabel, "setupNote")
    assert note.text() == "FlexWeek works around fixed times. Skip anything you don't have."
