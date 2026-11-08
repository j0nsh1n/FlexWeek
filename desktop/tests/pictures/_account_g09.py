"""Account pictures from the views lane's group G09: the sign-in, create-account and reset pages in the
smallest window. The lead gathers this fragment into screens_account.py."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from desktop.native.window import CREATE, RESET, SIGN_IN, NativeWindow
from desktop.tests.pictures.screen import Screen

SOURCES = ("desktop/native/window.py", "desktop/native/look.py")


def _entry_page(mode: str) -> Callable[[NativeWindow], None]:
    def prepare(window: NativeWindow) -> None:
        window._entry_mode = mode
        page = window.findChild(QWidget, "authPage")
        if page is not None:
            window._stack.setCurrentWidget(page)
        window._sync_auth_mode()

    return prepare


_FITS = (
    "At 1024 x 640 with Large text the page allows a 640 px window and the window keeps 1024 x 640. "
    "The card is whole inside its scroll area, every visible field is at least 48 px tall and the "
    "action button is at least 48 px tall, visible, and reachable by scrolling{whole}. "
)
_SPACING = (
    "At 1280 x 800 with Large text the spacing is unchanged: the page's outer spacing and margins are "
    "Qt's defaults, the card has no left margin, and the card spacing is {spacing}."
)

SCREENS: list[Screen] = [
    Screen(
        id="account.sign_in_small_window",
        area="account",
        prepare=_entry_page(SIGN_IN),
        checks=_FITS.format(whole=" (the whole sign-in card is visible without scrolling)")
        + _SPACING.format(spacing="the wide spacing (SPACING[3])"),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="account.create_account_small_window",
        area="account",
        prepare=_entry_page(CREATE),
        checks=_FITS.format(whole="") + _SPACING.format(spacing="the medium spacing (SPACING[2])"),
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="account.reset_password_small_window",
        area="account",
        prepare=_entry_page(RESET),
        checks=_FITS.format(whole="") + _SPACING.format(spacing="the tight spacing (SPACING[1])"),
        sources=SOURCES,
        main=True,
    ),
]
