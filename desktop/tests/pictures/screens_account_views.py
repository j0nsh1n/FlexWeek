"""The account screens the views lane wrote while moving the designs, Material shell and window chrome,
plus the Material 3 Sign in split showcase screen."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import show_material
from desktop.tests.pictures._collect import screens_of
from desktop.tests.pictures.screen import Screen

SIGN_IN_SOURCES = (
    "desktop/native/material/qml/account/AuthCard.qml",
    "desktop/native/material/qml/account/SignInShowcase.qml",
    "desktop/native/material/qml/account/AccountField.qml",
    "desktop/native/material/theme.py",
)


def _sign_in(window: NativeWindow) -> object:
    qapp = QApplication.instance()
    show_material(qapp, window)
    bridge = window._account_bridge()
    bridge.show_sign_in(clear=True)
    for _ in range(30):
        qapp.processEvents()
    return None


SCREENS = [
    *screens_of("account"),
    Screen(
        id="account.m3_sign_in",
        area="account",
        prepare=_sign_in,
        checks=(
            "Sign in split layout on desktop: left tonal welcome panel with QML-drawn FlexWeek scene, "
            "caption and indicator dots; right elevated sign-in form with Username, Password, Keep me "
            "signed in, Sign in, Forgot password and Create an account."
        ),
        sources=SIGN_IN_SOURCES,
        main=True,
        styles=("material",),
    ),
]
