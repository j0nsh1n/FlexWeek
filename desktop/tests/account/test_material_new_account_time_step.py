"""Material's first-run setup: the planning step opens on the 15-minute default time step, and an account
that skips setup still ends on 15. The server leaves 15 out of the preferences it sends."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.setup import HOMEWORK, WEEK
from desktop.tests.account.support import (
    LightLaunches,
    account,
    create,
    material_launches,  # noqa: F401
    settle,
    skip_setup,
    through_recovery,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_new_accounts_planning_step_opens_on_15_minutes(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "step_material")
    through_recovery(qapp, window)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == WEEK)
    settle(qapp, window)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == HOMEWORK)
    assert bridge.dragStep == 15
    bridge.setupNext()
    settle(qapp, window)
    assert window.session.preferences.get("drag_step_min", 15) == 15


def test_a_new_account_that_skips_setup_in_material_ends_on_15_minutes(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    create(qapp, window, "step_material_skip")
    through_recovery(qapp, window)
    skip_setup(qapp, window)
    assert window.session.preferences.get("drag_step_min", 15) == 15
    assert window.hand.step == 15
