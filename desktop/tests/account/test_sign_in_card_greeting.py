"""The sign-in card's heading is its one heading: "Sign in" on a first launch and on a return alike,
with no line of small print under it once someone has been here."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton

from desktop.native.kept import KeptSession
from desktop.native.window import NativeWindow
from desktop.tests.account.support import LightLaunches, light_launches, on_recovery_page, page  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import PASSWORD, USERNAME, qapp  # noqa: F401

FIRST = AGAIN = "Sign in"


def greeting(window: NativeWindow) -> str:
    """The card's heading, once it is the only one: no line of small print is shown under it."""
    assert window.auth_note.isHidden(), window.auth_note.text()
    return window.auth_heading.text()


def test_a_first_launch_and_a_return_both_say_sign_in(
    qapp: QApplication, light_launches: LightLaunches
) -> None:
    kept = light_launches.kept
    with light_launches.launched() as window:
        assert greeting(window) == FIRST
        on_recovery_page(qapp, window)
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        wait_until(qapp, lambda: not window.session.busy)
        window.session.logout()
        wait_until(qapp, lambda: page(window) == "authPage" and not window.session.busy)
        # Log out forgets the session, not that someone has been here.
        assert kept.token() is None
        assert greeting(window) == AGAIN
    with light_launches.launched() as window:
        assert greeting(window) == AGAIN
        window.findChild(QPushButton, "authSwitch").click()
        assert window.auth_note.text().startswith("FlexWeek fits homework around school and sports.")
        window.findChild(QPushButton, "authSwitch").click()
        assert greeting(window) == AGAIN


def test_signing_in_without_keeping_the_session_still_counts_as_having_been_here(
    qapp: QApplication, light_launches: LightLaunches, tmp_path: Path
) -> None:
    kept = light_launches.kept
    with light_launches.launched(KeptSession(tmp_path / "other" / "flexweek.json")) as window:
        on_recovery_page(qapp, window)
    with light_launches.launched() as window:
        assert greeting(window) == FIRST
        window.keep_signed_in.setChecked(False)
        window.username.setText(USERNAME)
        window.password.setText(PASSWORD)
        window.sign_in_button.click()
        wait_until(qapp, lambda: window.session.account is not None and not window.session.busy)
        assert kept.token() is None
    with light_launches.launched() as window:
        assert greeting(window) == AGAIN
