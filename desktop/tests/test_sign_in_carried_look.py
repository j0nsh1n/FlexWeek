"""N15: the screens shown before sign-in wear the last text size and High contrast, and nothing else."""

from __future__ import annotations

import contextlib
import json
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QStandardPaths
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from desktop.native.kept import KeptSession
from desktop.native.look import resolved_palette, sanitize_look
from desktop.native.window import NativeWindow
from desktop.server import LocalServer
from desktop.tests.logic_support import past_setup
from desktop.tests.window_support import PASSWORD, free, look_file, wait_until

LARGE = {"preset": "default", "knobs": {"text": "large"}}
LARGE_HIGH_CONTRAST = {"preset": "high-contrast", "knobs": {"text": "large"}}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-carried-look-test"])
    yield application


def page(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


def system_dark() -> bool:
    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


class Device:
    """One computer: a database, a kept-session folder and the windows opened on them."""

    def __init__(self, qapp: QApplication, folder: Path) -> None:
        self.qapp = qapp
        self.kept = KeptSession(folder / "signed-in" / "flexweek.json")
        self.server = LocalServer(folder / "flexweek.db")
        self.server.start()
        self.windows: list[NativeWindow] = []

    def open(self) -> NativeWindow:
        look_file().unlink(missing_ok=True)
        window = NativeWindow(self.server.origin, kept=self.kept)
        window.show()
        self.windows.append(window)
        return window

    def create_account(self, window: NativeWindow, name: str) -> None:
        window.username.setText(name)
        window.password.setText(PASSWORD)
        window.keep_signed_in.setChecked(False)
        window.create_button.click()
        wait_until(self.qapp, lambda: page(window) == "recoveryPage")
        window.recovery_ack.setChecked(True)
        window.recovery_continue.click()
        past_setup(self.qapp, window)

    def wear(self, window: NativeWindow, look: dict) -> None:
        window._look = sanitize_look(look)
        window.session.look = window._look
        window._save_look()

    def sign_out(self, window: NativeWindow) -> None:
        window.session.logout()
        wait_until(self.qapp, lambda: page(window) == "authPage" and window.session.account is None)
        for _ in range(10):
            self.qapp.processEvents()

    def close(self) -> None:
        for window in self.windows:
            with contextlib.suppress(RuntimeError):
                window.session.client.reset()
            window.hide()
            free(window)
        with contextlib.suppress(Exception):
            self.server.stop()
        look_file().unlink(missing_ok=True)


@pytest.fixture()
def device(qapp: QApplication, tmp_path: Path) -> Iterator[Device]:
    QStandardPaths.setTestModeEnabled(True)
    made = Device(qapp, tmp_path)
    yield made
    made.close()


def text_height(window: NativeWindow) -> int:
    window.username.ensurePolished()
    return window.username.fontMetrics().height()


def card_colour(window: NativeWindow) -> str:
    return window.styleSheet().split("QWidget#authCard { background: ")[1].split(";")[0]


# The file ----------------------------------------------------------------------------------------


def test_the_device_file_holds_only_the_text_size_the_contrast_and_the_owner(tmp_path: Path) -> None:
    kept = KeptSession(tmp_path / "signed-in" / "flexweek.json")
    assert kept.carried_look() is None
    kept.carry_look("acct-1", "large", True)
    assert kept.carried_look() == ("large", True)
    assert json.loads(kept.look.read_text()) == {"account": "acct-1", "text": "large", "contrast": True}
    assert stat.S_IMODE(kept.look.stat().st_mode) == 0o600
    assert kept.look.parent == kept.path.parent


@pytest.mark.parametrize(
    "body",
    ["", "not json", "[]", '{"text": "huge", "contrast": true}', '{"text": "large", "contrast": "yes"}'],
)
def test_a_damaged_device_file_reads_as_no_look(tmp_path: Path, body: str) -> None:
    kept = KeptSession(tmp_path / "flexweek.json")
    kept.look.write_text(body)
    assert kept.carried_look() is None


def test_forgetting_a_look_clears_it_only_for_its_own_account(tmp_path: Path) -> None:
    kept = KeptSession(tmp_path / "flexweek.json")
    kept.carry_look("acct-1", "large", True)
    kept.forget_look("acct-2")
    assert kept.carried_look() == ("large", True)
    kept.forget_look("acct-1")
    assert kept.carried_look() is None


# The sign-in screens -----------------------------------------------------------------------------


def test_signing_out_from_large_text_and_high_contrast_leaves_the_card_large_and_high_contrast(
    qapp: QApplication, device: Device
) -> None:
    w = device.open()
    plain_height, plain_card = text_height(w), card_colour(w)
    device.create_account(w, "carry_one")
    device.wear(w, LARGE_HIGH_CONTRAST)
    device.sign_out(w)
    assert text_height(w) > plain_height, "Large text was not carried to the sign-in card"
    assert w._worn_look() == sanitize_look(LARGE_HIGH_CONTRAST)
    expected = resolved_palette("system", system_dark(), sanitize_look(LARGE_HIGH_CONTRAST))["panel"]
    assert card_colour(w) == expected != plain_card, "High contrast was not carried to the sign-in card"
    for mode in ("create", "reset"):
        w._entry_mode = mode
        w._sync_auth_mode()
        assert w._worn_look() == sanitize_look(LARGE_HIGH_CONTRAST)
        assert card_colour(w) == expected


def test_text_size_alone_is_carried_without_high_contrast(qapp: QApplication, device: Device) -> None:
    w = device.open()
    device.create_account(w, "carry_two")
    device.wear(w, LARGE)
    device.sign_out(w)
    assert w._worn_look() == sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    assert card_colour(w) == resolved_palette("system", system_dark(), sanitize_look(None))["panel"]


def test_a_colour_pack_an_accent_and_a_style_are_not_carried(qapp: QApplication, device: Device) -> None:
    w = device.open()
    device.create_account(w, "carry_three")
    device.wear(w, {"preset": "paper", "knobs": {"text": "large", "corners": "rounded", "font": "mono"}})
    w.session.preferences = {**w.session.preferences, "theme_pack": "nocturne", "accent": "sea"}
    w._apply_appearance()
    device.sign_out(w)
    assert w._worn_look() == sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    assert w._look_inputs() == ("system", system_dark(), "default")
    assert json.loads(device.kept.look.read_text()).keys() == {"account", "text", "contrast"}


def test_a_fresh_computer_shows_the_default_look(qapp: QApplication, device: Device) -> None:
    w = device.open()
    assert device.kept.carried_look() is None
    assert w._worn_look() == sanitize_look(None)
    assert w._look_inputs() == ("system", system_dark(), "default")


def test_a_look_change_while_signed_in_is_carried_at_once(qapp: QApplication, device: Device) -> None:
    w = device.open()
    device.create_account(w, "carry_four")
    assert device.kept.carried_look() == ("normal", False)
    device.wear(w, {"preset": "default", "knobs": {"text": "small"}})
    assert device.kept.carried_look() == ("small", False)
    device.wear(w, LARGE_HIGH_CONTRAST)
    assert device.kept.carried_look() == ("large", True)


def test_log_out_keeps_the_file_and_the_next_launch_reads_it(qapp: QApplication, device: Device) -> None:
    w = device.open()
    device.create_account(w, "carry_five")
    device.wear(w, LARGE_HIGH_CONTRAST)
    device.sign_out(w)
    assert device.kept.carried_look() == ("large", True)
    again = device.open()
    assert again._worn_look() == sanitize_look(LARGE_HIGH_CONTRAST)


def test_deleting_the_account_clears_the_file_if_it_was_that_accounts(
    qapp: QApplication, device: Device
) -> None:
    w = device.open()
    device.create_account(w, "carry_six")
    device.wear(w, LARGE_HIGH_CONTRAST)
    w.session.delete_account(PASSWORD)
    wait_until(qapp, lambda: w.session.account is None and not w.session.busy)
    assert device.kept.carried_look() is None
    assert not device.kept.look.exists()


def test_deleting_an_account_leaves_a_look_that_another_account_wore(
    qapp: QApplication, device: Device
) -> None:
    w = device.open()
    device.create_account(w, "carry_seven")
    device.kept.carry_look("someone-else", "large", True)
    w.session.delete_account(PASSWORD)
    wait_until(qapp, lambda: w.session.account is None and not w.session.busy)
    assert device.kept.carried_look() == ("large", True)


def test_reset_password_fits_768_px_tall_at_large_text(qapp: QApplication, device: Device) -> None:
    device.kept.carry_look("someone", "large", False)
    w = device.open()
    w._entry_mode = "reset"
    w._sync_auth_mode()
    w.resize(1000, 768)
    for _ in range(5):
        qapp.processEvents()
    assert text_height(w) > 0
    assert w.height() == 768, "the window grew past a 768 px screen"
    card = w.username.parentWidget()
    bottom = card.mapTo(w, QPoint(0, card.height())).y()
    assert bottom <= 768, f"the Reset password card ends at {bottom}"
    assert w.recover_button.isVisible()
    assert w.recover_button.mapTo(w, QPoint(0, w.recover_button.height())).y() <= 768


# Signing in --------------------------------------------------------------------------------------


def test_the_sign_in_card_does_not_resize_or_flash_while_the_account_look_loads(
    qapp: QApplication, device: Device
) -> None:
    first = device.open()
    device.create_account(first, "carry_eight")
    device.sign_out(first)
    first.hide()
    # What the last student left: Large and High contrast. This account's own look is the plain one.
    device.kept.carry_look("someone-else", "large", True)
    w = device.open()
    large = sanitize_look(LARGE_HIGH_CONTRAST)
    assert w._worn_look() == large
    card = w.username.parentWidget()

    def seen() -> tuple:
        # The card's height also grows by the "Signing in…" line while that shows, which is not the look.
        height = None if w.auth_status.isVisible() else card.height()
        return (card.width(), height, text_height(w), w.styleSheet(), repr(w._worn_look()))

    before = seen()
    samples: list[tuple] = []
    w.username.setText("carry_eight")
    w.password.setText(PASSWORD)
    w.sign_in_button.click()

    def week_shown() -> bool:
        if page(w) == "authPage":
            samples.append(seen())
        return page(w) == "weekPage" and not w.session.busy

    wait_until(qapp, week_shown)
    assert samples, "the card was never on screen while signing in"
    names = ("width", "height", "text height", "style sheet", "worn look")
    changed = {
        names[i]
        for sample in samples
        for i in range(len(names))
        if sample[i] is not None and sample[i] != before[i]
    }
    assert not changed, f"the card changed in front of the student: {sorted(changed)}"
    for _ in range(10):
        qapp.processEvents()
    assert w._worn_look() is w._look, "the week does not wear the account's own look"
    assert w._worn_look() != large


def test_after_sign_in_the_week_wears_the_accounts_look_not_the_carried_one(
    qapp: QApplication, device: Device
) -> None:
    first = device.open()
    device.create_account(first, "carry_nine")
    device.sign_out(first)
    first.hide()
    device.kept.carry_look("someone-else", "large", True)
    w = device.open()
    w.username.setText("carry_nine")
    w.password.setText(PASSWORD)
    w.sign_in_button.click()
    wait_until(qapp, lambda: page(w) == "weekPage" and not w.session.busy)
    for _ in range(10):
        qapp.processEvents()
    assert w._look_inputs()[2] == (w.session.preferences or {}).get("accent", "default")
    assert w._worn_look() is w._look


def test_create_account_fits_768_px_tall_at_large_text(qapp: QApplication, device: Device) -> None:
    device.kept.carry_look("someone", "large", False)
    w = device.open()
    w._entry_mode = "create"
    w._sync_auth_mode()
    w.resize(1000, 768)
    for _ in range(5):
        qapp.processEvents()
    assert w.height() == 768, "the window grew past a 768 px screen"
    card = w._auth_card
    assert card.mapTo(w, QPoint(0, card.height())).y() <= 768
    assert w.create_button.mapTo(w, QPoint(0, w.create_button.height())).y() <= 768
