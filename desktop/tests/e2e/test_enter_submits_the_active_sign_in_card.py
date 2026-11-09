"""Enter on the sign-in, create-account or reset card does what its button does, and puts the keyboard on
the first field with a problem."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from desktop.native.window import CREATE, RESET, SIGN_IN, NativeWindow
from desktop.tests.window_support import qapp, server, signed_out  # noqa: F401


@pytest.mark.parametrize(
    ("mode", "field_name"),
    [(SIGN_IN, "password"), (CREATE, "password"), (RESET, "recovery_code")],
)
def test_enter_submits_the_active_auth_card_and_focuses_its_first_problem(
    qapp, signed_out: NativeWindow, mode: str, field_name: str
) -> None:
    card = signed_out
    card._entry_mode = mode
    card._sync_auth_mode()
    card.username.setText("jo" if mode == CREATE else "")
    card.password.setText("short" if mode == CREATE else "anything")
    card.recovery_code.setText("")
    card.new_recovery_password.setText("")
    field = getattr(card, field_name)
    field.setFocus()

    QTest.keyClick(field, Qt.Key.Key_Return)
    qapp.processEvents()

    assert card.focusWidget() is card.username
    assert card.username_problem.isVisible()
    enter_problem = card.username.accessibleDescription()

    card._clear_auth_problems()
    card.username.setText("jo" if mode == CREATE else "")
    card.password.setText("short" if mode == CREATE else "anything")
    card.recovery_code.setText("")
    card.new_recovery_password.setText("")
    {SIGN_IN: card.sign_in_button, CREATE: card.create_button, RESET: card.recover_button}[mode].click()
    qapp.processEvents()

    assert card.username.accessibleDescription() == enter_problem
    assert card.focusWidget() is card.username
