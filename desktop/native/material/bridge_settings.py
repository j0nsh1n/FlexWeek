"""The settings screen's bridge. The settings lane fills this file in later.

The way back to the Widgets styles stays a slot on the core bridge, because the
window already listens for that signal.
"""

from __future__ import annotations

from PySide6.QtCore import QObject


class SettingsBridge(QObject):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("settingsBridge")
