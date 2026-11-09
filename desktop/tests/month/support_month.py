"""What the Month tests share: the September month the old canvas tests used, the two blocks the
student has open, and a month grid inside a window that sends real mouse events."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from backend.month import build_month
from desktop.native.hours.hand import Hand, Verdict
from desktop.native.hours.month import MonthGrid
from desktop.native.weekmodel import build_week

MONDAY = "2026-09-21"
ESSAY = {
    "id": "essay-1",
    "title": "History essay",
    "kind": "flexible",
    "category": "homework",
    "assignment_id": "essay",
    "start": "19:00",
    "duration_min": 60,
    "days": [3],
    "pinned": True,
}
SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 390,
    "days": [0, 1, 2, 3, 4],
}


def september() -> dict:
    """September 2026 with two deadlines: the essay on a Sunday (no time), the oral at 09:00."""
    snapshot = build_month("2026-09", [], [])
    snapshot["deadlines"] = [
        {"id": "essay", "title": "History essay", "category": "assignments", "due": "2026-09-27"},
        {"id": "oral", "title": "French oral", "category": "assignments", "due": "2026-09-29T09:00"},
    ]
    for day in snapshot["days"]:
        day["due_ids"] = {"2026-09-27": ["essay"], "2026-09-29": ["oral"]}.get(day["date"], [])
    return snapshot


def club_day(snapshot: dict, iso: str, hours: range) -> None:
    """Fill one date of a month reply with an hour-long block for each hour."""
    day = next(item for item in snapshot["days"] if item["date"] == iso)
    day["blocks"] = [
        {"id": f"b{hour}", "title": f"Club {hour}", "start": f"{hour:02d}:00", "duration_min": 60}
        for hour in hours
    ]


class Stage:
    """A month in a window inside the offscreen screen, and what its hand reported."""

    def __init__(self, qapp: QApplication, judge=None) -> None:
        self.window = QWidget()
        self.window.setGeometry(0, 0, 1280, 720)
        self.said: list[object] = []
        self.hand = Hand(lambda block_id, from_day, span: Verdict(True, ""), self.window)
        self.hand.date_judge = judge
        self.hand.committed.connect(self.said.append)
        self.hand.refused.connect(lambda words: self.said.append(("refused", words)))
        self.grid = MonthGrid(self.window, hand=self.hand)
        self.grid.setGeometry(self.window.rect())
        self.opened: list[str] = []
        self.grid.day_activated.connect(self.opened.append)
        self.grid.set_week(build_week(MONDAY, [ESSAY, SCHOOL], {}, None))
        self.grid.set_month(september(), False)
        self.window.show()
        qapp.processEvents()
        self.canvas = self.grid.canvas

    def send(self, kind: QEvent.Type, at: QPoint, held: bool) -> None:
        buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
        event = QMouseEvent(
            kind,
            QPointF(self.canvas.mapFromGlobal(at)),
            QPointF(at),
            Qt.MouseButton.LeftButton,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(self.canvas, event)

    def carry(self, start: QPoint, end: QPoint, held=None) -> None:
        self.send(QEvent.Type.MouseButtonPress, start, True)
        for step in range(1, 9):
            self.send(QEvent.Type.MouseMove, start + (end - start) * step / 8, True)
        if held is not None:
            held()
        self.send(QEvent.Type.MouseButtonRelease, end, False)
