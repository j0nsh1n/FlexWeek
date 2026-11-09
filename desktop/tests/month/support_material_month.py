"""What the Material month tests share: finding the month's QML items, putting the account in the state
the month tests start from, and the small stand-ins the Settings month preview tests drive.

`bridge` and `panel` are small re-implementations of the helpers `_bridge` and `_panel` that
test_material_static_audit.py has; this folder keeps its own so it does not import a test module.
"""

from __future__ import annotations

import calendar
import copy
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.material.bridge_settings import PassiveMonthBridge
from desktop.native.window import NativeWindow
from desktop.tests.material_support import named, pump, show_material, visuals
from desktop.tests.waiting import wait_until


def bridge(window: NativeWindow) -> Any:
    return window._material_page.bridge


def panel(window: NativeWindow) -> Any:
    return window._material_page.bridge._settings_bridge


# The Material month on screen ---------------------------------------------------------------


def grid(first_of_month: date, sunday_first: bool = False) -> list[str]:
    """The dates a month shows: whole weeks from the week start to the week end around it."""
    days = calendar.monthrange(first_of_month.year, first_of_month.month)[1]
    last = first_of_month.replace(day=days)
    lead = (first_of_month.weekday() + (1 if sunday_first else 0)) % 7
    tail = (6 - (last.weekday() + (1 if sunday_first else 0)) % 7) % 7
    start = first_of_month - timedelta(days=lead)
    return [(start + timedelta(days=n)).isoformat() for n in range((last - start).days + tail + 1)]


def heading(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B')}"


def seed_school_and_essay(window: NativeWindow) -> None:
    """The clock at Thursday 19:00 of the week the account opened on, School on weekday mornings, and
    a History essay due on Sunday with its session at 18:45 on Thursday."""
    session = window.session
    CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=19))
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    wait_until(None, lambda: not session.busy and not session.dirty)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    wait_until(None, lambda: not session.busy and not session.dirty)


def cells(root: QObject) -> list[QObject]:
    return [item for item in visuals(root) if str(item.objectName()).startswith("monthDate-")]


def cell(root: QObject, iso: str) -> QObject:
    found = [item for item in cells(root) if str(item.objectName()) == f"monthDate-{iso}"]
    assert found, iso
    return found[0]


def shown_dates(root: QObject) -> list[str]:
    return [str(item.objectName())[len("monthDate-") :] for item in cells(root)]


def on_screen(item: QObject) -> bool:
    current = item
    while current is not None:
        visible = current.property("visible") if hasattr(current, "property") else None
        if visible is False:
            return False
        current = current.parentItem() if hasattr(current, "parentItem") else None
    return True


def texts(item: QObject, name: str) -> list[str]:
    return [
        str(child.property("text"))
        for child in visuals(item)
        if str(child.objectName()) == name and on_screen(child)
    ]


def named_on(item: QObject, name: str) -> list[QObject]:
    return [child for child in visuals(item) if str(child.objectName()) == name and on_screen(child)]


def click(quick: QObject, item: QObject, dx: float = 8, dy: float = 8) -> None:
    """A real press and release at a point inside the item, in the Quick widget's own coordinates."""
    point = item.mapToScene(QPointF(dx, dy))
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(int(point.x()), int(point.y())),
    )
    pump(QApplication.instance(), 10)


def open_month(qapp: QApplication, window: NativeWindow) -> tuple[QObject, QObject]:
    """Material on the month of the session's today. Returns the QML root and the month bridge."""
    root = show_material(qapp, window)
    month_bridge = bridge(window)
    month_bridge.showPage("month")
    month = month_bridge.property("month")
    here = window.session.today_iso()[:7]
    if window.session.selected_month != here:
        window.session.open_month(here)
    wait_until(qapp, lambda: (window.session.month_data or {}).get("month") == here)
    wait_until(qapp, lambda: len(cells(root)) > 0)
    pump(qapp)
    return root, month


# The Settings month preview -----------------------------------------------------------------


def idle(window: NativeWindow) -> bool:
    session = window.session
    return not session.busy and session.pending_save is None and not getattr(session.client, "pending", 0)


def hold_month_requests(window: NativeWindow) -> list[tuple[Any, ...]]:
    """Month requests the window makes from here on are kept in the returned list, unanswered, as
    (method, path, payload, ok, err); the test answers or fails them. The session's month cache is
    emptied first, as on a first visit, so the preview has to ask."""
    held: list[tuple[Any, ...]] = []
    client = window.session.client
    original = client.request
    window.session._month_cache.clear()

    def request(method: str, path: str, payload: Any, ok: Any, err: Any) -> Any:
        if path.startswith("/api/month"):
            held.append((method, path, payload, ok, err))
            return None
        return original(method, path, payload, ok, err)

    client.request = request
    return held


def preview_calls(held: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """The held requests that the Settings month preview made, oldest first."""
    return [call for call in held if "PassiveMonthBridge" in getattr(call[3], "__qualname__", "")]


def open_month_preview(qapp: QApplication, window: NativeWindow) -> tuple[QObject, Any, PassiveMonthBridge]:
    """Settings > Advanced on its Month preview. Returns the QML root, the settings bridge and the
    preview's own month bridge."""
    root = show_material(qapp, window)
    bridge(window).showPage("settings")
    settings = panel(window)
    settings.openAdvanced()
    settings.setPreviewView("month")
    return root, settings, settings._preview._passive_month


def preview_month(root: QObject) -> QObject | None:
    stage = named(root, "settingsPreviewMonth")
    found = named(stage[0], "materialMonth") if stage else []
    return found[0] if found else None


def totals(preview: PassiveMonthBridge) -> tuple[int, int]:
    return sum(r["plannedMin"] for r in preview.cellRows), sum(r["completedMin"] for r in preview.cellRows)


def state(s: Any) -> Any:
    """What a month preview must never change in the live session."""
    return copy.deepcopy(
        (
            s.planner_view,
            s.selected_day,
            s.selected_month,
            s.month_data,
            s.preferences,
            s.blocks,
            s.assignments,
            s.built_week(),
            s.unsaved_weeks(),
        )
    )


def snap(month: str = "2026-11", title: str = "A personal homework") -> dict[str, Any]:
    return {
        "month": month,
        "days": [
            {
                "date": f"{month}-23",
                "in_month": True,
                "blocks": [
                    {
                        "id": "personal",
                        "title": title,
                        "category": "homework",
                        "start": "17:00",
                        "duration_min": 75,
                        "completed": True,
                    }
                ],
            }
        ],
    }


# Stand-ins for the preview's unit tests -----------------------------------------------------

_LIVES: list[QObject] = []


def dispose_lives() -> None:
    while _LIVES:
        delete(_LIVES.pop())


class Live(QObject):
    changed = Signal()

    def __init__(self, session: Any) -> None:
        super().__init__()
        self.session = session
        _LIVES.append(self)

    def _session(self) -> Any:
        return self.session


class Emitter(QObject):
    week_changed = Signal()
    account_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        _LIVES.append(self)


class Held:
    """A client that keeps every request, for the test to answer or fail."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def request(self, *args: Any) -> None:
        self.calls.append(args)


def rig(qapp: Any) -> tuple[Any, Held, Live, PassiveMonthBridge]:
    """A signed-in session on 3 November 2026 with no month yet, a client that holds its requests,
    and the month preview on top of it."""
    held = Held()
    emitter = Emitter()
    session = SimpleNamespace(
        account={"id": "A"},
        selected_month=None,
        month_data=None,
        preferences={},
        week_start=None,
        unsaved_weeks=lambda: {},
        today_iso=lambda: "2026-11-03",
        _month_cache={},
        _month_gen=0,
        client=held,
        week_changed=emitter.week_changed,
        account_changed=emitter.account_changed,
    )
    live = Live(session)
    preview = PassiveMonthBridge(live, live)
    return session, held, live, preview
