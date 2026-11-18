"""Screens of the account area: the Account dialog's recovery-code line. Material's own sign-in, recovery
and setup screens are in screens_account_views.py and the account fragments."""

from __future__ import annotations

from desktop.native.settings import AccountDialog
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen


def account_dialog(remaining: int):
    def prepare(window: NativeWindow) -> AccountDialog:
        dialog = AccountDialog(window, remaining, {"username": "student"})
        dialog.show()
        return dialog

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="account.manage_account",
        area="account",
        prepare=account_dialog(8),
        sources=("desktop/native/settings.py", "desktop/native/look.py"),
        checks=(
            "With 8 recovery codes left, the line '8 unused recovery codes remain.' is drawn in the muted "
            "text colour, not the error red: codes left are an ordinary fact until there are none. The "
            "password boxes each show a Show password eye."
        ),
    ),
    Screen(
        id="account.manage_account_no_codes",
        area="account",
        prepare=account_dialog(0),
        sources=("desktop/native/settings.py", "desktop/native/look.py"),
        checks=(
            "With no recovery codes left, the line 'No unused recovery codes remain. Replace them before "
            "signing out.' is drawn in the error colour in a strong weight: it is a problem now. The "
            "contrast of that red on the dialog's background is readable."
        ),
    ),
]
