"""The My day screen's bridge. Same day board as Day, held to today."""

from __future__ import annotations

from PySide6.QtCore import QObject

from desktop.native.material.bridge_day import DayBridge


class MyDayBridge(DayBridge):
    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(window, parent, today_only=True)
        self.setObjectName("myDayBridge")
