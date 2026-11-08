"""Screens of the account area: the sign-in card, the recovery codes page after creating an account, and
the Account dialog's recovery-code line. The sign-in card and the recovery page are drawn in whichever
surface the renderer opened (the Widgets cards or the Material 3 card)."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from desktop.native.settings import AccountDialog
from desktop.native.window import NativeWindow
from desktop.tests.pictures import account_signin_screens
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until

PASSWORD = "a-long-test-password"
NEW_USERNAME = "picture_student"
SOURCES = (
    "desktop/native/window.py",
    "desktop/native/look.py",
    "desktop/native/client.py",
    "desktop/native/kept.py",
    "desktop/native/material/bridge_account.py",
    "desktop/native/material/qml/account",
)


def signed_out(window: NativeWindow) -> None:
    window.session.logout()
    wait_until(None, lambda: window.session.account is None and not window.session.busy)


def recovery_page(window: NativeWindow) -> None:
    """Sign out, then create a new account and stop on its recovery codes."""
    signed_out(window)
    bridge = window._account_bridge() if window._surface == "material" else None
    if bridge is not None:
        bridge.showCreate()
        bridge.setUsername(NEW_USERNAME)
        bridge.setPassword(PASSWORD)
        bridge.submit()
        wait_until(None, lambda: bridge.phase == "recovery")
        return
    if window.findChild(QPushButton, "createAccount").isHidden():
        window.findChild(QPushButton, "authSwitch").click()
    window.username.setText(NEW_USERNAME)
    window.password.setText(PASSWORD)
    window.findChild(QPushButton, "createAccount").click()
    wait_until(None, lambda: window._stack.currentWidget().objectName() == "recoveryPage")


def recovery_page_again(window: NativeWindow) -> None:
    """The Widgets recovery page after the first one was used and deleted, built again for new codes."""
    recovery_page(window)
    if window._surface == "material":
        return
    window.recovery_ack.setChecked(True)
    window.recovery_continue.click()
    wait_until(
        None, lambda: window._stack.currentWidget().objectName() != "recoveryPage" and not window.session.busy
    )
    window.session.recovery_codes.emit([f"{n}a2b-3c4d-5e6f-7a8{n}" for n in range(8)])


def account_dialog(remaining: int):
    def prepare(window: NativeWindow) -> AccountDialog:
        dialog = AccountDialog(window, remaining, {"username": "student"})
        dialog.show()
        return dialog

    return prepare


SCREENS: list[Screen] = [
    Screen(
        id="account.sign_in",
        area="account",
        prepare=signed_out,
        main=True,
        sources=SOURCES,
        checks=(
            "The card top never moves between Sign in, Create account and Reset your password. The FlexWeek "
            "icon is a 28 by 28 picture that comes first, to the left of the wordmark 'FlexWeek', and its "
            "centre lies within 4 pixels (vertically) of the wordmark's centre. The heading is the card's "
            "one heading, with no line of small print under it once someone has been here."
        ),
    ),
    Screen(
        id="account.recovery_codes",
        area="account",
        prepare=recovery_page,
        main=True,
        sources=SOURCES,
        checks=(
            "Eight codes, one per line, in the bundled JetBrains Mono face, every character of one width "
            "so 1 and l, 0 and O line up and read apart (iiii1111 as wide as WWWW0000, 1111 as wide as "
            "0000). The note over the codes is left-aligned like the codes, not centred over them. The "
            "FlexWeek icon sits to the left of the wordmark, 28 by 28, centred on it within 4 pixels."
        ),
    ),
    Screen(
        id="account.recovery_codes_again",
        area="account",
        prepare=recovery_page_again,
        sources=SOURCES,
        checks=(
            "The recovery page built again for new codes (from Account > New recovery codes) looks the "
            "same as the first time: the bundled JetBrains Mono face, left-aligned note and codes, the "
            "Copy and Save buttons styled like the first page's."
        ),
    ),
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

SCREENS = [*SCREENS, *account_signin_screens.SCREENS]
