"""The notes under the heading on Material's Create your account and Reset your password screens: the
backup reminder a new student sees, and what a student who lost their password is told about recovery
codes."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.tests.account.support import (
    LightLaunches,
    account,
    material_launches,  # noqa: F401
    qml,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_create_account_reminds_the_student_to_export_a_backup(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    account(window).showCreate()
    expected = (
        "FlexWeek fits homework around school and sports. "
        "Your week is saved on this computer, under this account. "
        "Export a backup file now and then (Settings > This computer > Manage account)."
    )
    wait_until(qapp, lambda: qml(window, "authNote").property("text") == expected, what="the Create note")


def test_reset_password_says_to_use_a_recovery_code_and_what_to_do_without_one(
    qapp: QApplication, material_launches: LightLaunches
) -> None:
    window = material_launches.launch()
    account(window).showReset()
    expected = (
        "Use one of the recovery codes you saved when you made your account. "
        "Lost them too? Create a new account and import a backup file, or start fresh."
    )
    wait_until(qapp, lambda: qml(window, "authNote").property("text") == expected, what="the Reset note")
    assert qml(window, "authHeading").property("text") == "Reset your password"


def test_the_sign_in_screen_has_no_note(qapp: QApplication, material_launches: LightLaunches) -> None:
    window = material_launches.launch()
    assert account(window).note == ""
