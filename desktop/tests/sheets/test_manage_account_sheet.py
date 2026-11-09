"""Manage account: every action is on the sheet, Change password is the one filled button, and the
action that deletes the account is the outlined red one. Where each label sits above its field and
whether Delete is cut off are looks: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from desktop.native.settings import AccountDialog
from desktop.tests.sheets.support_dialogs import shown, styled
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-manage-account-test"])


def test_manage_account_keeps_one_filled_button_and_its_actions(qapp: QApplication) -> None:
    parent, _palette = styled(qapp)
    account = shown(qapp, AccountDialog(parent, 8, {"username": "maya_r"}))
    for name in (
        "currentPassword",
        "newPassword",
        "changePassword",
        "recoveryCount",
        "replaceCodes",
        "exportAccount",
        "importAccount",
        "exportWeek",
        "exportDay",
        "importFile",
        "deleteAccount",
    ):
        assert account.findChild(QWidget, name) is not None, name
    loud = [
        button.objectName()
        for button in account.findChildren(QPushButton)
        if not (button.property("quiet") or button.property("outlined")) and button.objectName() != ""
    ]
    assert loud == ["changePassword"]
    free(account)
    free(parent)


def test_deleting_the_whole_account_is_an_outlined_red_action(qapp: QApplication) -> None:
    parent, _palette = styled(qapp)
    account = shown(qapp, AccountDialog(parent, 8, {"username": "maya_r"}))
    delete = account.findChild(QPushButton, "deleteAccount")
    assert delete.property("outlined") and delete.property("danger")
    free(account)
    free(parent)
