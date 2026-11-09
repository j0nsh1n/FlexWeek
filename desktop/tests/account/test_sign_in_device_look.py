"""The screens shown before sign-in wear the computer's own look, plus the text size and High contrast
the last student left, and nothing else; signing in puts the account's own look back. What the page looks
like in each case is in the sign-in screens (desktop/tests/pictures/screens_account_signin.py)."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QGuiApplication, QPalette

from desktop.native.look import sanitize_look
from desktop.native.window import ENTRY_PAGES, NativeWindow
from desktop.tests.account.support_signin import (  # noqa: F401
    LARGE,
    LARGE_HIGH_CONTRAST,
    MODES,
    Computer,
    computer,
    go,
    page,
    pump,
    signed_out,
    system_dark,
)
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, look_file, qapp  # noqa: F401

# The computer's own look.


def sign_out_from_a_pastel_account(qapp, window: NativeWindow) -> None:
    """A signed-in account whose look is Pastel, then Log out."""
    window._look = sanitize_look({"preset": "pastel"})
    window._apply_appearance()
    pump()
    assert window._worn_look() is window._look, "the account wears its own look"
    window.session.logout()
    wait_until(qapp, lambda: page(window) == "authPage" and not window.session.busy)
    pump()


def test_after_sign_out_the_page_is_the_devices_look_not_the_last_accounts(qapp, window) -> None:
    sign_out_from_a_pastel_account(qapp, window)
    assert window._look_inputs() == ("system", system_dark(), "default")
    assert window._worn_look() == sanitize_look(None)
    assert window._look["preset"] == "pastel", "the account's own look is still kept for its next sign-in"


def test_after_a_restart_the_page_is_the_devices_look_despite_a_stored_pastel(
    qapp, computer: Computer
) -> None:
    look_file().parent.mkdir(parents=True, exist_ok=True)
    look_file().write_text(json.dumps({"preset": "pastel", "knobs": {}}) + "\n")
    launched = computer.launch(keep_look_file=True)
    assert launched._look["preset"] == "pastel", "the stored look was read"
    assert launched._look_inputs() == ("system", system_dark(), "default")
    assert launched._worn_look() == sanitize_look(None)


def test_a_dark_computer_gets_the_dark_variant_of_the_sign_in_page_and_light_goes_back_to_light(
    qapp, signed_out: NativeWindow
) -> None:
    window = signed_out
    original = QGuiApplication.palette()
    dark = QPalette(original)
    dark.setColor(QPalette.ColorRole.Window, QColor("#202124"))
    QGuiApplication.setPalette(dark)
    try:
        assert window._look_inputs() == ("system", True, "default")
    finally:
        QGuiApplication.setPalette(original)
    was_dark = original.color(QPalette.ColorRole.Window).lightness() < 128
    assert window._look_inputs() == ("system", was_dark, "default")


def test_signing_in_puts_the_accounts_own_look_back_on(qapp, window) -> None:
    sign_out_from_a_pastel_account(qapp, window)
    assert window._wears_carried_look(), "signed out: the computer's look"
    window.username.setText(USERNAME)
    window.password.setText(PASSWORD)
    window.sign_in_button.click()
    wait_until(
        qapp,
        lambda: (
            window.session.account is not None
            and not window.session.busy
            and page(window) not in ENTRY_PAGES
        ),
    )
    pump()
    assert not window._wears_carried_look(), "signed in: the account's look"
    assert window._worn_look() is window._look
    assert window._look["preset"] == "pastel"


# What the last student leaves for the next.


def test_signing_out_from_large_text_and_high_contrast_leaves_the_card_large_and_high_contrast(
    qapp, computer: Computer
) -> None:
    w = computer.launch()
    assert w._worn_look() == sanitize_look(None)
    computer.create_account(w, "carry_one")
    computer.wear(w, LARGE_HIGH_CONTRAST)
    computer.sign_out(w)
    for mode in MODES:
        go(w, mode)
        assert w._worn_look() == sanitize_look(LARGE_HIGH_CONTRAST), mode


def test_text_size_alone_is_carried_without_high_contrast(qapp, computer: Computer) -> None:
    w = computer.launch()
    computer.create_account(w, "carry_two")
    computer.wear(w, LARGE)
    computer.sign_out(w)
    assert w._worn_look() == sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    assert w._worn_look()["preset"] == "default", "not High contrast"


def test_a_colour_pack_an_accent_and_a_style_are_not_carried(qapp, computer: Computer) -> None:
    w = computer.launch()
    computer.create_account(w, "carry_three")
    computer.wear(w, {"preset": "paper", "knobs": {"text": "large", "corners": "rounded", "font": "mono"}})
    w.session.preferences = {**w.session.preferences, "theme_pack": "nocturne", "accent": "sea"}
    w._apply_appearance()
    computer.sign_out(w)
    assert w._worn_look() == sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    assert w._look_inputs() == ("system", system_dark(), "default")
    assert json.loads(computer.kept.look.read_text()).keys() == {"account", "text", "contrast"}


def test_a_fresh_computer_shows_the_default_look(qapp, computer: Computer) -> None:
    w = computer.launch()
    assert computer.kept.carried_look() is None
    assert w._worn_look() == sanitize_look(None)
    assert w._look_inputs() == ("system", system_dark(), "default")


def test_a_look_change_while_signed_in_is_carried_at_once(qapp, computer: Computer) -> None:
    w = computer.launch()
    computer.create_account(w, "carry_four")
    assert computer.kept.carried_look() == ("normal", False)
    computer.wear(w, {"preset": "default", "knobs": {"text": "small"}})
    assert computer.kept.carried_look() == ("small", False)
    computer.wear(w, LARGE_HIGH_CONTRAST)
    assert computer.kept.carried_look() == ("large", True)


def test_log_out_keeps_the_file_and_the_next_launch_reads_it(qapp, computer: Computer) -> None:
    w = computer.launch()
    computer.create_account(w, "carry_five")
    computer.wear(w, LARGE_HIGH_CONTRAST)
    computer.sign_out(w)
    assert computer.kept.carried_look() == ("large", True)
    again = computer.relaunch(w)
    assert again._worn_look() == sanitize_look(LARGE_HIGH_CONTRAST)


def test_deleting_the_account_clears_the_file_if_it_was_that_accounts(qapp, computer: Computer) -> None:
    w = computer.launch()
    computer.create_account(w, "carry_six")
    computer.wear(w, LARGE_HIGH_CONTRAST)
    w.session.delete_account(PASSWORD)
    wait_until(qapp, lambda: w.session.account is None and not w.session.busy)
    assert computer.kept.carried_look() is None
    assert not computer.kept.look.exists()


def test_deleting_an_account_leaves_a_look_that_another_account_wore(qapp, computer: Computer) -> None:
    w = computer.launch()
    computer.create_account(w, "carry_seven")
    computer.kept.carry_look("someone-else", "large", True)
    w.session.delete_account(PASSWORD)
    wait_until(qapp, lambda: w.session.account is None and not w.session.busy)
    assert computer.kept.carried_look() == ("large", True)


# Signing in.


def test_after_sign_in_the_week_wears_the_accounts_look_not_the_carried_one(
    qapp, computer: Computer
) -> None:
    first = computer.launch()
    computer.create_account(first, "carry_nine")
    computer.sign_out(first)
    computer.kept.carry_look("someone-else", "large", True)
    w = computer.relaunch(first)
    w.username.setText("carry_nine")
    w.password.setText(PASSWORD)
    w.sign_in_button.click()
    wait_until(qapp, lambda: page(w) == "weekPage" and not w.session.busy)
    pump()
    assert w._look_inputs()[2] == (w.session.preferences or {}).get("accent", "default")
    assert w._worn_look() is w._look
