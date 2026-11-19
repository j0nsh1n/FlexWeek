"""What the week-view tests share: the week every layout test builds from, and the helpers that
put a light window in a known week. Qt is imported inside the helpers so the data can be imported
where it is absent."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from desktop.native.controller import NativeSession

WEEK = "2026-09-14"
HOMEWORK = {
    "chem": {"id": "chem", "title": "Chem lab report", "due": "2026-09-17T23:59", "completed": False},
    "essay": {"id": "essay", "title": "History essay", "due": "2026-09-18T21:00", "completed": False},
    "poster": {"id": "poster", "title": "Science fair poster", "due": "2026-09-20T20:00", "completed": False},
    "math": {"id": "math", "title": "Math worksheet", "due": "2026-09-15T08:00", "completed": True},
}


def block(
    block_id: str, kind: str, days: list[int], start: str | None, minutes: int, **extra: object
) -> dict:
    return {
        "id": block_id,
        "title": extra.pop("title", block_id.title()),
        "kind": kind,
        "category": extra.pop("category", "class" if kind == "locked" else "assignments"),
        "days": days,
        "start": start,
        "duration_min": minutes,
        **extra,
    }


BLOCKS = [
    block("school", "locked", [0, 1, 2, 3, 4], "08:00", 390),
    block("dinner", "locked", [0, 1, 2, 3, 4, 5, 6], "18:00", 30, category="meals"),
    block("chem-1", "flexible", [3], None, 90, assignment_id="chem"),
    block("essay-1", "flexible", [3], "18:45", 60, assignment_id="essay"),
    block("poster-1", "flexible", [], None, 120, assignment_id="poster"),
    block("math-1", "flexible", [0, 1], "15:45", 45, assignment_id="math", completed=True, completed_day=0),
]
TRACE = {
    "placed": [block("chem-1", "flexible", [3], "20:00", 90, assignment_id="chem")],
    "unplaced": [block("poster-1", "flexible", [], None, 120, assignment_id="poster")],
    "explanations": [
        {
            "block_id": "chem-1",
            "message": "Finishes only 2 h 29 min before it's due.",
            "slack_min": 149,
            "slack_status": "danger",
        },
        {
            "block_id": "essay-1",
            "message": "Finishes 25 h 15 min before it's due.",
            "slack_min": 1515,
            "slack_status": "tight",
        },
        {
            "block_id": "poster-1",
            "message": "There isn't enough time left before it's due, even with nothing else planned.",
            "reason": "DEADLINE_MISS",
        },
    ],
}

EVENT_PASSES = 10  # Event-loop turns that let a resize or a look change reach every child.


def pump(qapp: QApplication, passes: int = 5) -> None:
    """Hand the posted events a few turns, so a resize reaches the rail and the buttons."""
    for _ in range(passes):
        qapp.processEvents()


def send_mouse(widget, kind, at: QPoint, held: bool) -> None:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    local = QPointF(widget.mapFromGlobal(at))
    buttons = Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton
    event = QMouseEvent(
        kind, local, QPointF(at), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(widget, event)


















def settled_session(qapp: QApplication, session: NativeSession) -> None:
    """The foreground request and the replies the light client still has on their way are done."""
    from desktop.tests.waiting import wait_until

    wait_until(
        qapp,
        lambda: not session.busy and not getattr(session.client, "pending", 0),
        what="the session settling",
    )


def fail_once(session: NativeSession, method: str, path: str, status: int = 503) -> None:
    """Refuse the next matching request the way the client reports a real reply with that status.
    Nothing reaches the backend, which is what a 503 means for a write: nothing was stored."""
    from PySide6.QtCore import QTimer

    from desktop.native.client import _error

    real = session.client.request

    def request(verb, target, payload, on_success, on_error):
        if verb != method or not target.startswith(path):
            return real(verb, target, payload, on_success, on_error)
        session.client.request = real  # type: ignore[method-assign]
        QTimer.singleShot(0, lambda: on_error(_error(status)))
        return None

    session.client.request = request  # type: ignore[method-assign]


def fixed(block_id: str, title: str, day: int, start: str) -> dict:
    return {
        "id": block_id,
        "title": title,
        "kind": "locked",
        "duration_min": 60,
        "days": [day],
        "start": start,
    }


def titles(blocks: list[dict]) -> list[str]:
    return [item["title"] for item in blocks]






