"""A new account starts with a 15-minute time step; an account that never chose one keeps dragging in fives.

A new account is one made in this sitting. Its setup shows 15 on the planning page, skipping setup keeps
15, and picking 5 there keeps 5. Accounts from before (signed in, not just made) are left as they were.
"""

# ruff: noqa: F811
# Fixtures are imported by name, so a test taking one as an argument redefines it.
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.setup import HOMEWORK
from desktop.tests.setup.support_new_account import (
    Launcher,
    launcher,  # noqa: F401
    new_account,
    page,
    sign_in,
    written,
)
from desktop.tests.window_support import qapp  # noqa: F401


def _to_planning_page(qapp: QApplication, window) -> None:
    """Style, then Your week (School as it opens), then the planning page."""
    setup = window.setup_page
    setup.next.click()
    written(qapp, window)
    setup.school_times.set_span("08:00", 390)
    setup.next.click()
    written(qapp, window)
    assert setup.step == HOMEWORK


def test_a_new_accounts_planning_page_opens_on_15_minutes_and_keeps_it(
    qapp: QApplication, launcher: Launcher
) -> None:
    window = new_account(qapp, launcher, "step_new")
    _to_planning_page(qapp, window)
    setup = window.setup_page
    assert setup.drag_buttons[15].isChecked()
    setup.next.click()
    written(qapp, window)
    assert window.session.preferences["drag_step_min"] == 15
    assert window.hand.step == 15


def test_a_new_account_that_skips_setup_still_ends_on_15_minutes(
    qapp: QApplication, launcher: Launcher
) -> None:
    window = new_account(qapp, launcher, "step_skipper")
    window.setup_page.skip_all.click()
    written(qapp, window)
    assert page(window) == "weekPage"
    assert window.session.preferences["drag_step_min"] == 15
    assert window.hand.step == 15


def test_a_new_account_that_picks_5_keeps_5_and_is_dragged_in_fives_when_it_signs_in_again(
    qapp: QApplication, launcher: Launcher
) -> None:
    window = new_account(qapp, launcher, "step_five")
    _to_planning_page(qapp, window)
    window.setup_page.drag_buttons[5].setChecked(True)
    window.setup_page.next.click()
    written(qapp, window)
    window.setup_page.skip_all.click()
    written(qapp, window)
    # The server leaves 5 out of what it sends back, as it does for an account that never chose.
    assert window.session.preferences.get("drag_step_min", 5) == 5
    assert window.hand.step == 5
    launcher.quit(window)

    again = sign_in(qapp, launcher, "step_five")
    assert again.session.preferences.get("drag_step_min", 5) == 5
    assert again.hand.step == 5
    # Running setup again for an account that is not new shows what it has: 5.
    assert again._setup_state(False).preferences.get("drag_step_min", 5) == 5
    again._run_setup_again()
    again.setup_page.skip_all.click()
    written(qapp, again)
    assert again.session.preferences.get("drag_step_min", 5) == 5
