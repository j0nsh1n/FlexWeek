"""The My day screen's bridge. That lane fills this file in later."""

from __future__ import annotations

from PySide6.QtCore import QObject


class MyDayBridge(QObject):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("myDayBridge")
