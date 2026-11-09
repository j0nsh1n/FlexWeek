"""The clock choice on setup's week page: a new account ends with the 12-hour clock unless it picks
24-hour, a skip or a quit keeps the choice off the screen, and an older account that never chose stays
on the 24-hour clock it had."""

# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.setup import DONE, WEEK, SetupPage, SetupState
from desktop.native.weekmodel import clock_text, set_clock_24h
from desktop.tests.setup.support_new_account import (
    Launcher,
    launcher,  # noqa: F401
    new_account,
    sign_in,
    written,
)
from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def the_clock_is_left_on_12_hour() -> Iterator[None]:
    """The clock choice is one setting for the whole process, so one test's 24-hour clock would be the
    next test's."""
    set_clock_24h(False)
    yield
    set_clock_24h(False)


def bare_page() -> SetupPage:
    setup = SetupPage()
    setup.open(SetupState("system", sanitize_look(None), sanitize_layout(None), {}, [], ""), WEEK)
    return setup


def test_a_new_account_that_leaves_the_clock_alone_ends_with_a_12_hour_clock(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_clock_default")
    setup = window.setup_page
    setup.style_cards["dashboard"].chosen.emit()
    setup.next.click()
    assert setup.step == WEEK
    assert setup.clock_buttons[False].isChecked(), "12-hour is picked before the student chooses"
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences.get("clock_24h", False) is False
    assert clock_text(15 * 60 + 30) == "3:30 PM"
    launcher.quit(window)

    again = sign_in(qapp, launcher, "setup_clock_default")
    assert again.session.preferences.get("clock_24h", False) is False
    assert clock_text(15 * 60 + 30) == "3:30 PM"


def test_skipping_the_clock_page_still_gives_a_new_account_a_12_hour_clock(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    window = new_account(qapp, launcher, "setup_clock_skipped")
    setup = window.setup_page
    while setup.step != DONE:
        setup.skip.click()
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences.get("clock_24h", False) is False
    assert clock_text(15 * 60 + 30) == "3:30 PM"


def test_choosing_24_hour_in_setup_sticks(qapp: QApplication, launcher: Launcher) -> None:
    window = new_account(qapp, launcher, "setup_clock_24")
    setup = window.setup_page
    setup.style_cards["dashboard"].chosen.emit()
    setup.next.click()
    setup.clock_buttons[True].setChecked(True)
    assert clock_text(15 * 60 + 30) == "15:30", "the page's own times follow the choice at once"
    assert setup.school_times.start.displayFormat() == "HH:mm"
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences["clock_24h"] is True
    assert clock_text(15 * 60 + 30) == "15:30"
    launcher.quit(window)

    again = sign_in(qapp, launcher, "setup_clock_24")
    assert again.session.preferences["clock_24h"] is True
    assert clock_text(15 * 60 + 30) == "15:30"


def test_home_and_end_pick_the_12_and_24_hour_clock(qapp: QApplication) -> None:
    """Home and End move between the two clock radios, as the arrows do."""
    setup = bare_page()
    assert setup.clock_buttons[False].isChecked()
    QTest.keyClick(setup.clock_buttons[False], Qt.Key.Key_End)
    assert setup.clock_buttons[True].isChecked()
    assert clock_text(15 * 60) == "15:00"
    QTest.keyClick(setup.clock_buttons[True], Qt.Key.Key_Home)
    assert setup.clock_buttons[False].isChecked()
    assert clock_text(15 * 60) == "3:00 PM"
    setup.deleteLater()


def test_a_clock_tried_and_skipped_on_the_page_is_put_back(qapp: QApplication) -> None:
    setup = bare_page()
    assert setup.clock_buttons[False].isChecked()
    setup.clock_buttons[True].setChecked(True)
    assert clock_text(15 * 60) == "15:00"
    setup.skip.click()
    assert setup.clock_buttons[False].isChecked()
    assert clock_text(15 * 60) == "3:00 PM"
    setup.deleteLater()


def test_a_clock_tried_and_then_skip_setup_is_put_back(qapp: QApplication) -> None:
    """Skip setup keeps nothing, so the 24-hour clock tried on the Week page must not stay on screen."""
    setup = bare_page()
    setup.clock_buttons[True].setChecked(True)
    assert clock_text(15 * 60) == "15:00"
    setup.skip_all.click()
    assert clock_text(15 * 60) == "3:00 PM"
    setup.deleteLater()


def test_an_account_from_before_the_clock_choice_that_never_chose_stays_on_24_hour(
    qapp: QApplication,
    launcher: Launcher,
) -> None:
    """An older version sent no clock for a 24-hour account; the update must not turn that into 12-hour."""
    window = new_account(qapp, launcher, "setup_clock_veteran")
    window.setup_page.skip_all.click()
    written(qapp, window)
    launcher.quit(window)
    launcher.stop_backend()
    with sqlite3.connect(launcher.database) as db:
        db.execute("UPDATE preferences SET prefs_version = 1, comfort_json = '{}'")
    launcher.start_backend()

    again = sign_in(qapp, launcher, "setup_clock_veteran")
    assert again.session.preferences.get("clock_24h") is True
    assert clock_text(15 * 60 + 30) == "15:30"
