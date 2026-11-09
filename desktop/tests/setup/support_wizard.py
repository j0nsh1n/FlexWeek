"""What the setup tests share: the page on its own, opened on a state of the student's choosing."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import monday_of
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.setup import WEEK, SetupPage, SetupState

__all__ = ["WEEK", "opened", "state"]


def state(**changes: object) -> SetupState:
    base = SetupState(
        pack="system",
        look={"preset": "default", "knobs": {}},
        layout=sanitize_layout(None),
        preferences={},
        blocks=[],
        week_start=monday_of("2026-09-23"),
    )
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def opened(qapp: QApplication, **changes: object) -> SetupPage:
    setup = SetupPage()
    setup.motion = "off"
    setup.resize(1100, 720)
    setup.open(state(**changes))
    setup.show()
    qapp.processEvents()
    return setup
