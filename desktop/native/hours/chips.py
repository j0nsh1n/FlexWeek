"""Things outside the hours that can be dragged onto them."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QPushButton, QWidget

from desktop.native.hours.hand import Gesture, Hand, Held
from desktop.native.weekmodel import Waiting, length_label


class TrayChip(QPushButton):
    """Homework with no time yet. Drag it onto any hours to give it that time; a click opens it."""

    def __init__(self, hand: Hand, waiting: Waiting, parent: QWidget | None = None) -> None:
        super().__init__(f"{waiting.title} · {length_label(waiting.minutes)}", parent)
        self.hand = hand
        self.block_id = waiting.block_id
        self.held = Held(Gesture.PLACE, waiting.title, waiting.minutes, waiting.block_id)
        self.setProperty("block_id", waiting.block_id)
        self.setProperty("tray", True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Drag onto the hours to give it a time, or click to open it")

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        # Not passed on: a press may be the start of a drag, so the click waits for the release.
        self.hand.press(self, self.held, event.globalPosition().toPoint(), tap=self.click)
