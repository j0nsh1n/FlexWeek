"""The month screen's bridge. The month lane fills this file in later."""

from __future__ import annotations

from PySide6.QtCore import QObject


class MonthBridge(QObject):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("monthBridge")
