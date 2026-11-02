"""The day screen's bridge. The day lane fills this file in later."""

from __future__ import annotations

from PySide6.QtCore import QObject


class DayBridge(QObject):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("dayBridge")
