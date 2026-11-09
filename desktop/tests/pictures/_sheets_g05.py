"""Screens for the dialog an alarm rings in."""

from __future__ import annotations

from typing import TYPE_CHECKING

from desktop.tests.pictures.screen import Screen

if TYPE_CHECKING:
    from desktop.native.window import NativeWindow


def _alarm_ringing(window: NativeWindow) -> object:
    from desktop.native.settings import AlarmRingDialog

    dialog = AlarmRingDialog(window, {"name": "Wake up", "time": "06:45", "sound": "chime"}, "")
    # The window keeps the dialog it is ringing in, as when an alarm really rings.
    window._alarm_dialog = dialog
    dialog.show()
    dialog.adjustSize()
    return dialog


SCREENS: list[Screen] = [
    Screen(
        id="sheets.alarm_ringing",
        area="sheets",
        prepare=_alarm_ringing,
        checks=(
            "The ringing alarm is big enough to notice: at least 380 px wide (it once came up 209 px "
            "wide, narrower than the notification it replaces, and was easy to miss). Snooze and "
            "Dismiss are each at least 44 px high, side by side; Dismiss is the filled button and "
            "Snooze is the quiet one, and the title and the time line read clearly above them."
        ),
        sources=("desktop/native/settings.py",),
    ),
]
