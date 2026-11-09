"""What the week-view tests share: the week every layout test builds from, and the helpers that
put a light window in a known week. Qt is imported inside the helpers so the data can be imported
where it is absent."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from desktop.native.controller import NativeSession
    from desktop.native.window import NativeWindow

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

CLASSIC_ONE_DAY = {"main": "classic", "day": "one", "options": {}}
SMALL_WINDOW = (1024, 640)  # The smallest supported window.
NORMAL_WINDOW = (1280, 800)
EVENT_PASSES = 10  # Event-loop turns that let a resize or a look change reach every child.
HOMEWORK_DAY = 1  # Tuesday, after the Monday the week starts on.
PLAN_DEADLINE_HOUR = 8  # Due before the week can fit any work.
HOMEWORK_MINUTES = 60
POSTER_MINUTES = 600  # Ten hours ensures the solver reports the plan result actions.
PLAN_BUTTONS = ("planReviewDetails", "planReviewReplan", "planReviewDismiss")
WAITING_WORDS = "No time yet · drag onto a day"


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


def set_text_size(window: NativeWindow, size: str, *, carried: bool = False) -> None:
    """Text `size` for this window; `carried` also hands the look to the session, as a saved
    choice would."""
    from desktop.native.look import sanitize_look

    window._look = sanitize_look({"preset": "default", "knobs": {"text": size}})
    if carried:
        window.session.look = window._look
        window._carry_look()
    window._apply_appearance()
    if not carried:
        window._sync_chrome()


def show_large_classic(qapp: QApplication, window: NativeWindow, width: int, height: int) -> None:
    """The classic week at `width` x `height` with Large text, settled."""
    from desktop.native.layouts.registry import sanitize_layout

    set_text_size(window, "large", carried=True)
    window._layout = sanitize_layout(CLASSIC_ONE_DAY)
    window._apply_appearance()
    window._on_week()
    window.resize(width, height)
    window.show()
    pump(qapp, EVENT_PASSES)


def add_waiting_poster(qapp: QApplication, window: NativeWindow) -> dict:
    """Poster, 30 min, due Sunday and not yet on any day: the homework the folded rail lists."""
    from desktop.native.calendar import sunday_due
    from desktop.tests.window_support import settled

    window.session.add_homework(
        {
            "id": "poster",
            "title": "Poster",
            "due": sunday_due(window.session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    window.session.save()
    settled(qapp, window)
    return next(item for item in window.session.blocks if item.get("assignment_id") == "poster")


def put_math_essay_on_wednesday(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    """The classic Week view with a Math worksheet pinned on Wednesday 17:00 for 45 min. The
    worksheet sits on Wednesday: a later clock in the week cannot move it onto an earlier day
    ("That time has passed"), and a placed block is pinned the way a hand move saves it."""
    from PySide6.QtWidgets import QAbstractButton

    from desktop.native.calendar import sunday_due
    from desktop.tests.window_support import settled

    session = window.session
    window.resize(1280, 860)
    window._layout = dict(CLASSIC_ONE_DAY)
    session.add_homework(
        {
            "id": "math",
            "title": "Math worksheet",
            "due": sunday_due(session.week_start),
            "estimate_min": 45,
            "revision": 0,
        }
    )
    placed = next(item for item in session.blocks if item.get("assignment_id") == "math")
    session.add_block({**placed, "start": "17:00", "days": [2], "pinned": True})
    session.save()
    settled(qapp, window)
    window.findChild(QAbstractButton, "viewWeek").click()
    settled(qapp, window)
    return window


@pytest.fixture()
def essay_week(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    return put_math_essay_on_wednesday(qapp, window)


def put_two_homeworks_on_tuesday(qapp: QApplication, window: NativeWindow) -> None:
    """History essay at 09:00 and Biology lab report at 10:00 on Tuesday, one hour each, with the
    clock on Tuesday 08:00 so both are still to come."""
    from datetime import datetime, timedelta

    from backend.tests.fake_clock import CLOCK
    from desktop.tests.window_support import settled

    session = window.session
    monday = datetime.fromisoformat(session.week_start)
    CLOCK.set(monday + timedelta(days=HOMEWORK_DAY, hours=PLAN_DEADLINE_HOUR))
    due = (monday + timedelta(days=HOMEWORK_DAY)).strftime("%Y-%m-%dT23:59")
    for key, title in (("history", "History essay"), ("biology", "Biology lab report")):
        session.add_homework(
            {"id": key, "title": title, "due": due, "estimate_min": HOMEWORK_MINUTES, "revision": 0}
        )
    session.save()
    settled(qapp, window)
    for key, start in (("history", "09:00"), ("biology", "10:00")):
        placed = next(item for item in session.blocks if item.get("assignment_id") == key)
        session.add_block({**placed, "start": start, "days": [HOMEWORK_DAY], "pinned": True})
    session.save()
    settled(qapp, window)


def plan_poster_that_cannot_fit(qapp: QApplication, window: NativeWindow) -> None:
    """A ten-hour poster due Monday 08:00 cannot fit, so planning ends on the plan result."""
    from datetime import date

    from desktop.tests.window_support import settled

    session = window.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "poster",
            "title": "Science fair poster",
            "due": f"{monday.isoformat()}T{PLAN_DEADLINE_HOUR:02d}:00",
            "estimate_min": POSTER_MINUTES,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    session.solve()
    settled(qapp, window)


@pytest.fixture()
def menus(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict]:
    """Every menu the window would open is recorded (its rows) and not shown."""
    from desktop.native import window as window_module
    from desktop.native.menus import Menu

    seen: dict = {"rows": []}

    class Shown(Menu):
        def exec(self, at: QPoint | None = None, *_rest: object) -> object:
            seen["rows"].append([a.text() or "---" for a in self.actions()])
            return None

    monkeypatch.setattr(window_module, "Menu", Shown)
    yield seen


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
