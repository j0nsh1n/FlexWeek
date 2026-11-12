"""Material's first-run setup: the planning step opens on the 15-minute default time step, an account that
skips setup still ends on 15, and a 5 picked there is stored. The server leaves 15 out of the preferences
it sends."""

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
from desktop.tests.settings.support_material_settings import _named, _open_settings
from desktop.tests.settings.test_material_dragging_step import _widgets_choice
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


def test_a_5_picked_in_materials_setup_is_stored_and_both_looks_settings_show_it(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    bridge = account(window)
    create(qapp, window, "step_material_five")
    through_recovery(qapp, window)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == WEEK)
    settle(qapp, window)
    bridge.setupNext()
    wait_until(qapp, lambda: bridge.setupStep == HOMEWORK)
    bridge.setDragStep(5)
    assert bridge.dragStep == 5
    bridge.setupNext()
    settle(qapp, window)
    # 15 is the default and is left out of the stored preferences, so a 5 is present only if it was kept.
    assert window.session.preferences["drag_step_min"] == 5
    assert window.hand.step == 5
    root = _open_settings(qapp, window, "planning")
    wait_until(qapp, lambda: _named(root, "dragStep")[0].property("current") == "5")
    assert _widgets_choice(window) == 5
