"""Screens of the sign-in card (Widgets): the three pages, the password box and its eye, a wrong
sign-in, the focused box, a link under the pointer and under the keyboard, the card at Large text and in
High contrast, and the page after a student with another look signed out. The lead merges this file into
screens_account.py.

Every screen starts from the light window the renderer opened signed in, and signs out in `prepare`.
The sign-in page wears only the computer's own look plus the text size and High contrast the last student
left (window._worn_look), so the Large text and High contrast screens set that carried look the way the
kept-session file would (`window._carried`)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

from desktop.native.client import SIGN_IN_WRONG
from desktop.native.look import auth_rules, effective_look, resolved_palette, sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

SOURCES = (
    "desktop/native/window.py",
    "desktop/native/look.py",
    "desktop/native/widgets.py",
    "desktop/native/fields.py",
    "desktop/native/tokens.py",
)
PASSWORD_TEXT = "a-long-test-password"

PAGE_COLOURS = (
    "The page behind the card is the computer's own look, System pack: #f7f8fa in the light variant, "
    "#111315 in the dark one."
)
SAME_TOP = (
    "The wordmark and the top edge of the card are at the same height as on the other two sign-in pages "
    "(compare account.signin-sign-in, account.signin-create and account.signin-reset), so nothing jumps "
    "when the student switches page; the pinned position is the one the tallest page (Create or Reset) "
    "needs, centred with as much room above the wordmark as under that card, and the shorter pages simply "
    "end sooner, not stretched to Create's height."
)
SHADOW = (
    "The card is a sheet lifted with the large shadow: its corners are clearly rounder than a 10 px "
    "card's (a 16 px sheet radius), and the shadow is not cut off by the card's holder: the page is "
    "darker 4, 16 and 28 px under the card than 60 px under it."
)
EDGES = (
    "The edge of the Username and Password boxes reads at 3 to 1 or better against the box's own fill and "
    "against the card behind it, in both the light and the dark variant."
)


def _settle() -> None:
    for _ in range(4):
        QApplication.processEvents()


def _signed_out(
    window: NativeWindow, mode: str = "sign in", carried: tuple[str, bool] | None = None
) -> None:
    """Log out and show the sign-in card on `mode`. `carried` is the text size and High contrast the
    last student left, as the kept-session file holds them."""
    window.session.logout()
    wait_until(None, lambda: window.session.account is None and not window.session.busy, what="signing out")
    if carried is not None:
        window._carried = carried
        window._apply_appearance()
    window._entry_mode = mode
    window._sync_auth_mode()
    _settle()
    still(window)


def _page(mode: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        _signed_out(window, mode)
        return None

    return prepare


def _password_box(window: NativeWindow) -> object:
    _signed_out(window)
    window.password.setText(PASSWORD_TEXT)
    _settle()
    return window.password


def _password_shown(window: NativeWindow) -> object:
    _signed_out(window)
    window.password.setText(PASSWORD_TEXT)
    window.password_reveal.setChecked(True)
    _settle()
    return window.password


def _wrong_sign_in(window: NativeWindow) -> object:
    _signed_out(window)
    window._on_status(SIGN_IN_WRONG)
    _settle()
    return None


def _focused_username(window: NativeWindow) -> object:
    _signed_out(window)
    window.activateWindow()
    wait_until(None, window.isActiveWindow, what="the window becoming active")
    window.username.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    return None


def _pale_accent_field(window: NativeWindow) -> object:
    """A typed pale accent painted through the same auth field rule the window uses (sign-in keeps the
    computer's look, so a typed accent is not otherwise reachable on this page)."""
    _signed_out(window)
    look = sanitize_look({"custom": {"name": "Lime", "base": "light", "accent": "#dfff00"}})
    card = QWidget(window)
    card.setObjectName("authCard")
    field = QLineEdit(card)
    field.setObjectName("username")
    field.setGeometry(8, 8, 200, 36)
    card.setStyleSheet(auth_rules(resolved_palette("system", False, look), effective_look(look), 6, 10))
    card.resize(220, 52)
    card.move(20, 20)
    card.show()
    card.raise_()
    window.activateWindow()
    wait_until(None, window.isActiveWindow, what="the window becoming active")
    field.setFocus(Qt.FocusReason.TabFocusReason)
    _settle()
    return card


def _link(name: str, how: str) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        _signed_out(window)
        link = window.findChild(QPushButton, name)
        if how == "keyboard":
            window.activateWindow()
            wait_until(None, window.isActiveWindow, what="the window becoming active")
            link.setFocus(Qt.FocusReason.TabFocusReason)
        else:
            QTest.mouseMove(link, link.rect().center())
        _settle()
        return link

    return prepare


def _carried_look(mode: str, carried: tuple[str, bool], tall: bool) -> Callable[[NativeWindow], object]:
    def prepare(window: NativeWindow) -> object:
        if tall:
            window.resize(1000, 768)
        _signed_out(window, mode, carried)
        return None

    return prepare


def _recovery_card(window: NativeWindow) -> object:
    _signed_out(window)
    window.username.setText("shadow_check")
    window.password.setText(PASSWORD_TEXT)
    window.create_button.click()
    wait_until(
        None,
        lambda: window._stack.currentWidget().objectName() == "recoveryPage",
        what="the recovery codes page",
    )
    _settle()
    still(window)
    return None


def _after_pastel_account(window: NativeWindow) -> object:
    window._look = sanitize_look({"preset": "pastel"})
    window._apply_appearance()
    _settle()
    _signed_out(window)
    return None


LARGE = (
    "Large text is carried from the last student: every label, check box and button on the card is whole, "
    "none cut off sideways or underneath (a wrapped label is as tall as its words need at its width, any "
    "other part at least as large as it asks for), and the card is as wide as its words, 420 px times the "
    "text scale, not the 420 px of Normal text. The card keeps the plain panel colour (High contrast was "
    "not carried)."
)
HIGH_CONTRAST = (
    "The text is Large and the card wears High contrast's panel colour (not the plain one), with sharp "
    "corners; being a look with hard edges and no soft depth, the card paints no shadow, so the page just "
    "below the card is the page's own colour, the same as at the window's corner. Nothing is cut off."
)
FITS_768 = (
    "In a 1000 by 768 window the window does not grow past 768 px: the card ends at 768 px or higher up, "
    "and so does the {button} button."
)


def _large_and_high_contrast_screens() -> list[Screen]:
    made: list[Screen] = []
    buttons = {"sign in": "Sign in", "create": "Create account", "reset": "Reset password"}
    for mode in ("sign in", "create", "reset"):
        slug = mode.replace(" ", "-")
        fits = FITS_768.format(button=buttons[mode]) if mode != "sign in" else ""
        made.append(
            Screen(
                id=f"account.signin-large-text-{slug}",
                area="account",
                prepare=_carried_look(mode, ("large", False), tall=mode != "sign in"),
                checks=(LARGE + " " + fits).strip(),
                sources=SOURCES,
            )
        )
        made.append(
            Screen(
                id=f"account.signin-high-contrast-{slug}",
                area="account",
                prepare=_carried_look(mode, ("large", True), tall=mode != "sign in"),
                checks=(HIGH_CONTRAST + " " + fits).strip(),
                sources=SOURCES,
            )
        )
    return made


def _link_screens() -> list[Screen]:
    made: list[Screen] = []
    words = {"forgotPassword": "Forgot password", "authSwitch": "New here? Create an account"}
    for name, label in words.items():
        for how in ("pointer", "keyboard"):
            slug = "forgot-password" if name == "forgotPassword" else "create-account"
            made.append(
                Screen(
                    id=f"account.signin-link-{slug}-{how}",
                    area="account",
                    prepare=_link(name, how),
                    checks=(
                        f'The "{label}" link, reached with the {how}: it is underlined across nearly the '
                        "whole width of its words (so the colour is not the only sign), darker than the "
                        "same link at rest in account.signin-sign-in, and still the accent colour, "
                        "clearly not near-black text. It does not go near-black on hover, and a link "
                        "reached with the keyboard shows the same change (it once showed nothing)."
                    ),
                    sources=SOURCES,
                )
            )
    return made


SCREENS: list[Screen] = [
    Screen(
        id="account.signin-sign-in",
        area="account",
        prepare=_page("sign in"),
        main=True,
        checks=(
            "The Sign in page. One heading, \"Sign in\", with no second line of small print under it, and "
            "the name FlexWeek only in the wordmark above the card. The wordmark (icon beside FlexWeek) "
            "is on the page above the card, not inside it, centred over it (its box centre within 2 px "
            "of the card's centre). " + SAME_TOP + " " + PAGE_COLOURS + " A Pastel page from the last "
            "student's account must not show. " + SHADOW + " Under the Sign in button are two links: "
            "\"New here? Create an account\" is "
            "heavier (semibold) than \"Forgot password\" (regular weight), because most students on a "
            "first run need the first; at rest both are the accent colour and not underlined. "
            + EDGES
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-create",
        area="account",
        prepare=_page("create"),
        checks=(
            "The Create account page: heading \"Create your account\" with its small print under it, no "
            "Forgot password link (a new account has no password to forget). Each hint sits 4 px under "
            "its own box (the username hint under Username, the password hint under Password) and 16 "
            "px of card spacing lies between the username hint and the Password caption, and between "
            "the password hint and the Keep me signed in box. " + SAME_TOP + " The Create card is "
            "taller than the Sign in card. " + SHADOW + " " + EDGES + " The eye sits inside the password "
            "box at its right edge, wholly inside it."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-reset",
        area="account",
        prepare=_page("reset"),
        checks=(
            "The Reset your password page: one filled button (Reset password), no Sign in or Create "
            "account button, no Password box (only the recovery code and the new password are asked "
            "for), a Back to sign in link. " + SAME_TOP
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-password-eye",
        area="account",
        prepare=_password_box,
        checks=(
            "The password box with a typed password hidden as dots. The eye is inside the box at its "
            "right edge (within 12 px of it), wholly inside the box, in a 32 by 32 px button with a 24 px "
            "glyph (the drawn glyph 18 to 24 px wide), its darkest ink reading at 3 to 1 or better against "
            "the box's fill. The box is as wide as the Username box above it (the card's full width), not "
            "76 px narrower for a Show button beside it."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-password-shown",
        area="account",
        prepare=_password_shown,
        checks=(
            "The eye switched on: the typed password is readable as plain text and the eye is drawn "
            "crossed out (Hide password), still inside the box."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-wrong-password",
        area="account",
        prepare=_wrong_sign_in,
        checks=(
            "A wrong sign-in: a short line under the Password box, 4 px under it, with the error mark "
            "beside the words, the words in the error colour and no box around them (the top row of "
            "the line holds no error-coloured edge). The long sentence is not also at the foot of the "
            "card."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-focused-field",
        area="account",
        prepare=_focused_username,
        checks=(
            "The Username box has the keyboard: its edge shows the accent colour (each channel within "
            "8 of the accent)."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-pale-accent-field",
        area="account",
        prepare=_pale_accent_field,
        checks=(
            "A focused box under a pale typed accent (#dfff00, a light yellow-green): its edge is the "
            "readable focus edge the look computes (accent darkened until it reads at 3 to 1 on the "
            "box and the card), not the pale accent itself."
        ),
        sources=SOURCES,
    ),
    *_link_screens(),
    *_large_and_high_contrast_screens(),
    Screen(
        id="account.signin-recovery-card",
        area="account",
        prepare=_recovery_card,
        checks=(
            "The recovery codes card that follows Create account is drawn like the sign-in card: " + SHADOW
        ),
        sources=SOURCES,
    ),
    Screen(
        id="account.signin-after-pastel-account",
        area="account",
        prepare=_after_pastel_account,
        checks=(
            "A student whose look is Pastel signed out: the sign-in page is the computer's own look "
            "(#f7f8fa light, #111315 dark), not the Pastel page (#f3ecff). The same holds after the "
            "app is restarted with a Pastel look stored on this computer."
        ),
        sources=SOURCES,
    ),
]
