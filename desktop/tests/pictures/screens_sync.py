"""Screens of the sync area: the Devices card in Settings > This computer, the pairing and removing
sheets, and the sync status dot. A stand-in service answers the card, so no network endpoint is opened
to draw them."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QPushButton, QScrollArea, QWidget

from desktop.native import devices
from desktop.native.devices import DevicesPanel, SyncHost
from desktop.native.settings import SECTIONS
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still

SOURCES = ("desktop/native/devices.py", "desktop/native/settings.py")
PHONE = "Pixel"


class StandInService:
    """What the Devices card asks a sync service: its phones, its status, and a pairing code."""

    def __init__(self, phones: list[dict]) -> None:
        self._phones = phones

    def peers(self, _user_id: int) -> list[dict]:
        return [dict(row) for row in self._phones]

    def status(self) -> dict:
        return {"syncing": False, "last_error": None, "last_sync_ms": None}

    def generation(self) -> int:
        return 0

    def pair_start(self, _user_id: int) -> dict:
        return {"display_code": "4827 1903", "qr": "flexweek://pair/2?c=48271903"}

    def pair_status(self) -> dict:
        # Less than a second past 5 minutes, so the sheet always reads "Code works for 4:59".
        return {"state": "waiting", "expires_at_ms": devices._now_ms() + 299_999, "tries_left": 3}

    def pair_cancel(self) -> None:
        return None


def linked_phone() -> dict:
    return {
        "device_id": "phone-1",
        "name": PHONE,
        "last_seen": str(devices._now_ms()),
        "revoked": 0,
    }


def devices_panel(window: NativeWindow, phones: list[dict] | None) -> DevicesPanel:
    """Settings > This computer with a sync host: `phones` None is a computer whose service has not
    started, a list is a running service holding those phones."""
    host = SyncHost(Path("flexweek.db"))
    if phones is not None:
        host.service = StandInService(phones)  # type: ignore[assignment]
    window.session.use_sync_host(host)
    window._sync_host = host
    host.setParent(window)
    window._open_settings_at(SECTIONS.index("This computer"))
    still(window)
    panel = window._settings.findChild(DevicesPanel)
    parent: QWidget | None = panel.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(panel)
            break
        parent = parent.parentWidget()
    return panel


def card_with_no_phone(window: NativeWindow) -> object:
    devices_panel(window, None)
    still(window)
    return None


def card_with_a_phone(window: NativeWindow) -> object:
    devices_panel(window, [linked_phone()])
    still(window)
    return None


def card_with_problems(window: NativeWindow) -> object:
    panel = devices_panel(window, [linked_phone()])
    panel._synced([("phone-1", {"clock_skewed": 2}, None), ("phone-2", None, RuntimeError("no route"))], None)
    still(window)
    return None


def pairing_sheet(window: NativeWindow) -> object:
    panel = devices_panel(window, [])
    panel.pair_button.click()

    def code_is_shown() -> bool:
        return panel.dialog is not None and re.fullmatch(r"\d{4} \d{4}", panel.dialog.code.text()) is not None

    wait_until(None, code_is_shown)
    still(window)
    return None


def removing_sheet(window: NativeWindow) -> object:
    panel = devices_panel(window, [linked_phone()])
    panel.findChild(QPushButton, "removePhone").click()
    still(window)
    return None


def sync_dot_with_a_problem(window: NativeWindow) -> object:
    window.sync_dot.show_state("problem")
    still(window)
    return window.sync_dot.parentWidget()


SCREENS: list[Screen] = [
    Screen(
        id="sync.devices_card_no_phone",
        area="sync",
        prepare=card_with_no_phone,
        checks=(
            "Settings > This computer > Devices says 'No phone is linked yet.' in one wrapped line; "
            "Pair a phone is an enabled outline button and Sync now is drawn disabled. The relay "
            "sentence under them wraps inside the card; Settings never scrolls sideways (the card's "
            "text is not cut off at the right edge)."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sync.devices_card_phone",
        area="sync",
        prepare=card_with_a_phone,
        checks=(
            "The linked phone's row reads: its name (Pixel), 'Synced just now' filling the middle, "
            "and an outline Remove button at the right, all on one baseline. Pair a phone and Sync "
            "now are both enabled. The relay sentence wraps inside the card."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sync.devices_card_problems",
        area="sync",
        prepare=card_with_problems,
        checks=(
            "Above the buttons, the clock warning ('Your phone's clock looks wrong. 2 changes were "
            "held back.') and the line 'Could not reach your phone. Make sure FlexWeek is open on it.' "
            "both wrap inside the card, are readable against its background, and do not overlap "
            "the phone row or the buttons."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sync.pairing_sheet",
        area="sync",
        prepare=pairing_sheet,
        checks=(
            "The Pair a phone sheet shows the code (4827 1903) in large type, at least 24 pt and "
            "clearly the biggest text on the sheet, with 'Code works for 4:59. 3 tries left.' below "
            "it. There is no 'scan the code' text and no box holding a code to copy. Cancel is "
            "drawn and New code is disabled. Nothing is clipped."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sync.removing_sheet",
        area="sync",
        prepare=removing_sheet,
        checks=(
            "The sheet titled 'Remove Pixel?' explains that the phone keeps what it has. Keep phone "
            "is an outline button and Remove phone is the red (danger) one; the red button reads "
            "as the destructive choice, and the sheet's text is not clipped."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sync.status_dot_problem",
        area="sync",
        prepare=sync_dot_with_a_problem,
        checks=(
            "The 10 px sync dot in the status strip is filled with the look's error colour when sync "
            "has a problem, so it reads as a problem in every look, light and dark, and stays visible "
            "against the strip behind it. It is round and is not cut off."
        ),
        sources=SOURCES,
    ),
]
