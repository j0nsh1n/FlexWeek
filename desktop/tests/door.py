"""The test door (2.0.0 plan, P3): the Python app, started for tests, answers a screen test's steps over a
local socket file, so a screen test written in Rust (flexweek-testkit's Door) can run against the app that is
known to work. One JSON object per line each way; every line asked gets one line answered, in order.
Test-only; it goes with the Python host.

Steps (each answers {"ok": true, ...} or {"ok": false, "error": "..."}):
  click {target}            a left click at the middle of a visible item, as the pointer does it
  key {key}                 a key press in the window: a Qt key name without "Key_" ("Return", "Down"),
                            after "ctrl+", "shift+" or "alt+" for a key held with them ("ctrl+N")
  type {text}               the text typed, one key at a time, into the item that has the keyboard
  focus {target}            give the item the keyboard, where a test starts keys from
  read {target}             {found, name, text, enabled, focused, visible}
  property {target, name}   {value}: one property of the item, as JSON (a QML list or object as its plain
                            values; text for anything else)
  read_all {target}         {items: [read ...]}: every item with that name or those words, shown or not
  focused                   the item with the keyboard: {found, chain: [{name, title}] from it outwards,
                            ring (its focus ring is shown), in_view (wholly inside its scroller or window)}
  drag {target, by, at?}    press at the middle of an item (moved by `at`, [dx, dy]), move by `by` in
                            twelve steps and let go, as the pointer does it
  wheel {target, dy, key?}  the mouse wheel over an item, `dy` in wheel units, with "ctrl" and so on held
  pump {turns}              let the window run that many turns of its event loop
  app                       {week_start, selected_month, screen, busy, dirty, snack, sheet,
                            window_has_keyboard, blocks, homework}:
                            what the session holds (the Python host's stand-in for the view state the Rust
                            core will expose)
Setting up, not a student's steps (the Rust core's seeds and fake clock stand in for these later):
  seed {name}               "material_week": School Monday to Friday 08:00-14:30, the History essay planned
                            for Thursday 18:45, weekends shown, the 24-hour clock, the clock at Thursday 19:00
  homework {id, title, minutes, due}   homework added and saved
  block {block}             a block added (or replaced, by id) and saved
  clock {at}                the fake clock held at `at` (ISO local time) and the window's clock tick run
  preferences {values}      preferences changed as Settings would (the clock format too) and the window told
  open_day {day}            the Day screen on that date (ISO)
  set_property {target, name, value}  one property of an item set (a scroller's contentY)
  reveal {target}           the scroller holding the item scrolled so it shows with 120 px around it (where
                            the hours open depends on the clock; a drag must start on screen)
  slot_error                a slot that raises on the next turn of the event loop (the door's own test of
                            the report below)
A target is {"name": objectName} or {"words": the text a student reads}, optionally with "within": the
objectName of the item to look inside (the "20" in the date picker's month, not another "20"), and with a
name, "title": only the item of that name with that title (the week block "Club"). Names are looked for
among painted items first, so a Repeater's rows are found too.

An error raised inside a Qt slot, at start or while the app ran between steps or during one, fails the next
step's answer, as the Python suite fails a test on one; it is also printed, so it is never lost.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QAccessible, QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import quick_of

# Readable as JSON; anything else is given as its text.
PLAIN = (str, int, float, bool, type(None))


class StepRefused(Exception):
    """A step that cannot be done now (no such item, an unknown key); the test hears why."""


def _visuals(item: QObject) -> list[QObject]:
    """The item and every painted child (Repeater rows are visual children, not QObject children)."""
    found = [item]
    for child in item.childItems() if hasattr(item, "childItems") else ():
        found.extend(_visuals(child))
    return found


MODIFIERS = {
    "ctrl": Qt.KeyboardModifier.ControlModifier,
    "shift": Qt.KeyboardModifier.ShiftModifier,
    "alt": Qt.KeyboardModifier.AltModifier,
}


class SlotErrors:
    """Errors raised inside Qt slots, kept from before the door opens until a step's answer reports them."""

    def __init__(self) -> None:
        self.raised: list[str] = []
        sys.excepthook = self.record

    def record(self, kind: type[BaseException], error: BaseException, trace: object) -> None:
        told = "".join(traceback.format_exception(kind, error, trace))  # type: ignore[arg-type]
        print(told, file=sys.stderr, flush=True)
        self.raised.append(told)


def _named(root: QObject, name: str) -> QObject | None:
    if not name:
        return None
    for item in _visuals(root):
        if str(item.objectName() or "") == name:
            return item
    return root.findChild(QObject, name)


class Door(QObject):
    """Answers one test at a time on `path`, on the window's thread."""

    def __init__(self, window: NativeWindow, path: str, slot_errors: SlotErrors) -> None:
        super().__init__(window)
        self._window = window
        self._buffer = b""
        self._busy = False
        self._socket: QLocalSocket | None = None
        self._slot_errors = slot_errors
        QLocalServer.removeServer(path)
        self._server = QLocalServer(self)
        if not self._server.listen(path):
            raise RuntimeError(f"the test door could not listen on {path}: {self._server.errorString()}")
        self._server.newConnection.connect(self._accept)
        self._steps: dict[str, Callable[[dict], dict]] = {
            "click": self._click,
            "key": self._key,
            "type": self._type,
            "focus": self._focus,
            "read": self._read,
            "property": self._property,
            "read_all": self._read_all,
            "focused": self._focused,
            "drag": self._drag,
            "wheel": self._wheel,
            "pump": self._pump,
            "app": self._app,
            "slot_error": self._slot_error,
            "seed": self._seed,
            "homework": self._homework,
            "block": self._block,
            "clock": self._clock,
            "preferences": self._preferences,
            "open_day": self._open_day,
            "set_property": self._set_property,
            "reveal": self._reveal,
        }

    def _accept(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        if self._socket is not None:
            self._socket.readyRead.disconnect(self._incoming)
            self._socket.disconnectFromServer()
        self._socket = socket
        self._buffer = b""
        socket.readyRead.connect(self._incoming)

    def _incoming(self) -> None:
        socket = self._socket
        if socket is None:
            return
        self._buffer += bytes(socket.readAll().data())
        # A step runs the event loop, which may call this again: the outer call answers every line, in order.
        if self._busy:
            return
        self._busy = True
        try:
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                answer = json.dumps(self._answer(line)).encode() + b"\n"
                # A new connection while the step ran takes over: this answer belonged to the old one.
                if socket is not self._socket:
                    return
                socket.write(answer)
                socket.flush()
        finally:
            self._busy = False

    def _answer(self, line: bytes) -> dict:
        try:
            asked = json.loads(line)
            if not isinstance(asked, dict):
                raise StepRefused("a step is a JSON object")
            step = self._steps.get(str(asked.get("step", "")))
            if step is None:
                raise StepRefused(f"no step called {asked.get('step')!r}")
            answer = {"ok": True, **step(asked)}
        except Exception as error:  # every line gets an answer; the test hears what went wrong
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
        if self._slot_errors.raised:
            raised = "\n".join(self._slot_errors.raised)
            self._slot_errors.raised.clear()
            return {"ok": False, "error": f"an error was raised inside a Qt slot:\n{raised}"}
        return answer

    # The window's parts.

    def _host(self) -> Any:
        page = quick_of(self._window)
        if page is None:
            raise StepRefused("the Material window is not built")
        return page

    def _root(self, target: object) -> QObject | None:
        if not isinstance(target, dict):
            raise StepRefused("a target is a JSON object")
        if "name" not in target and "words" not in target:
            raise StepRefused("a target names an item or its words")
        root = self._host().rootObject()
        if root is None:
            return None
        if "within" in target:
            return _named(root, str(target["within"]))
        return root

    def _find(self, target: object) -> QObject | None:
        root = self._root(target)
        if root is None:
            return None
        assert isinstance(target, dict)
        if "name" in target and "title" in target:
            found = self._find_all(target)
            return found[0] if found else None
        if "name" in target:
            return _named(root, str(target["name"]))
        words = str(target["words"])
        for item in _visuals(root):
            text = item.property("text")
            if isinstance(text, str) and text == words and item.isVisible():
                return item
        return None

    def _find_all(self, target: object) -> list[QObject]:
        root = self._root(target)
        if root is None:
            return []
        assert isinstance(target, dict)
        if "name" in target:
            name = str(target["name"])
            found = [item for item in _visuals(root) if str(item.objectName() or "") == name]
            if "title" in target:
                found = [item for item in found if item.property("title") == target["title"]]
            return found
        words = str(target["words"])
        return [item for item in _visuals(root) if item.property("text") == words]

    def _item(self, asked: dict) -> QObject:
        item = self._find(asked.get("target"))
        if item is None:
            raise StepRefused(f"nothing on screen is {asked.get('target')}")
        return item

    def _turns(self, count: int) -> None:
        application = QApplication.instance()
        for _ in range(count):
            application.processEvents()

    # The steps.

    def _click(self, asked: dict) -> dict:
        item = self._item(asked)
        if not (hasattr(item, "isVisible") and item.isVisible()):
            raise StepRefused(f"{asked.get('target')} is not on screen")
        spot = item.mapToScene(item.boundingRect().center())
        QTest.mouseClick(self._host(), Qt.MouseButton.LeftButton, pos=QPoint(int(spot.x()), int(spot.y())))
        self._turns(10)
        return {}

    def _key(self, asked: dict) -> dict:
        *held, name = str(asked["key"]).split("+")
        modifiers = _modifiers("+".join(held))
        key = getattr(Qt.Key, f"Key_{name}", None)
        if key is None:
            raise StepRefused(f"no key called {name!r}")
        QTest.keyClick(self._host(), key, modifiers)
        self._turns(10)
        return {}

    def _type(self, asked: dict) -> dict:
        # QTest.keyClicks takes widgets only; Material is a Qt Quick window, so each character is its own key.
        for character in str(asked["text"]):
            QTest.keyClick(self._host(), character)
        self._turns(10)
        return {}

    def _focus(self, asked: dict) -> dict:
        self._item(asked).forceActiveFocus()
        self._turns(5)
        return {}

    def _read(self, asked: dict) -> dict:
        item = self._find(asked.get("target"))
        if item is None:
            return {"found": False}
        return _seen(item)

    def _read_all(self, asked: dict) -> dict:
        return {"items": [_seen(item) for item in self._find_all(asked.get("target"))]}

    def _focused(self, _asked: dict) -> dict:
        item = self._host().activeFocusItem()
        if item is None:
            return {"found": False}
        chain = []
        outer = item
        while outer is not None:
            title = outer.property("title")
            chain.append(
                {"name": str(outer.objectName() or ""), "title": title if isinstance(title, str) else ""}
            )
            outer = outer.parentItem()
        return {
            "found": True,
            "chain": chain,
            "ring": _ring_shown(item),
            "in_view": self._in_view(item),
            **_seen(item),
        }

    def _in_view(self, item: QObject) -> bool:
        """Wholly inside the nearest scroller holding it (2 px of slack), or inside the window."""
        root = self._host().rootObject()
        height = float(item.property("height") or 0)
        outer = item.parentItem()
        while outer is not None and outer is not root:
            content = outer.property("contentItem")
            if outer.property("contentY") is not None and isinstance(content, QObject):
                top = float(item.mapToItem(content, 0, 0).y())
                content_y = float(outer.property("contentY"))
                bottom = content_y + float(outer.property("height"))
                return top >= content_y - 2 and top + height <= bottom + 2
            outer = outer.parentItem()
        top = float(item.mapToItem(root, 0, 0).y())
        return top >= -2 and top + height <= float(root.property("height")) + 2

    def _property(self, asked: dict) -> dict:
        value = self._item(asked).property(str(asked["name"]))
        if hasattr(value, "toVariant"):  # a QML list or object (a menu's entries) as plain values
            value = value.toVariant()
            try:
                json.dumps(value)
            except TypeError, ValueError:
                value = str(value)
            return {"value": value}
        if isinstance(value, float) and not math.isfinite(value):
            return {"value": str(value)}
        return {"value": value if isinstance(value, PLAIN) else str(value)}

    def _point(self, asked: dict) -> QPoint:
        item = self._item(asked)
        if not (hasattr(item, "isVisible") and item.isVisible()):
            raise StepRefused(f"{asked.get('target')} is not on screen")
        dx, dy = _pair(asked.get("at"))
        spot = item.mapToScene(item.boundingRect().center())
        return QPoint(int(spot.x()) + dx, int(spot.y()) + dy)

    def _drag(self, asked: dict) -> dict:
        host = self._host()
        start = self._point(asked)
        dx, dy = _pair(asked.get("by"))
        QTest.mousePress(host, Qt.MouseButton.LeftButton, pos=start)
        self._turns(4)
        steps = 12
        for step in range(1, steps + 1):
            QTest.mouseMove(host, QPoint(start.x() + dx * step // steps, start.y() + dy * step // steps))
            self._turns(2)
        QTest.mouseRelease(host, Qt.MouseButton.LeftButton, pos=QPoint(start.x() + dx, start.y() + dy))
        self._turns(10)
        self._settle()
        return {}

    def _wheel(self, asked: dict) -> dict:
        from PySide6.QtGui import QWheelEvent

        spot = self._point(asked)
        modifiers = _modifiers(str(asked.get("key") or ""))
        steps = int(asked.get("dy") or 0)
        host = self._host()
        event = QWheelEvent(
            QPointF(spot),
            QPointF(host.mapToGlobal(spot)),
            QPoint(0, 0),
            QPoint(0, 120 * steps),
            Qt.MouseButton.NoButton,
            modifiers,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(host, event)
        self._turns(10)
        return {}

    def _pump(self, asked: dict) -> dict:
        self._turns(int(asked.get("turns") or 10))
        return {}

    def _slot_error(self, _asked: dict) -> dict:
        def raises() -> None:
            raise RuntimeError("raised on purpose by the door's slot_error step")

        QTimer.singleShot(0, raises)
        return {}

    def _app(self, _asked: dict) -> dict:
        session = self._window.session
        bridge = self._host().bridge
        sheets = getattr(bridge, "sheets", None)
        return {
            "week_start": session.week_start,
            "selected_month": session.selected_month,
            "screen": str(bridge.screen),
            "busy": bool(session.busy),
            "dirty": bool(session.dirty),
            "snack": str(bridge.property("snackText") or ""),
            "sheet": str(sheets.kind) if sheets is not None else "",
            "window_has_keyboard": QGuiApplication.focusWindow() is self._host(),
            "blocks": [{field: block.get(field) for field in BLOCK_FIELDS} for block in session.blocks],
            "homework": [
                {"id": key, "title": item.get("title"), "completed": bool(item.get("completed"))}
                for key, item in session.assignments.items()
            ],
        }

    # Setting up.

    def _settle(self) -> None:
        from desktop.tests.window_support import settled

        settled(QApplication.instance(), self._window)
        self._host().bridge.refresh()
        self._turns(10)

    def _seed(self, asked: dict) -> dict:
        name = str(asked.get("name"))
        if name != "material_week":
            raise StepRefused(f"no seed called {name!r}")
        from desktop.tests.sheets.support_material_sheets import material_week

        material_week(QApplication.instance(), self._window)
        self._window.home_week = self._window.session.week_start
        self._turns(10)
        return {}

    def _homework(self, asked: dict) -> dict:
        self._window.session.add_homework(
            {
                "id": str(asked["id"]),
                "title": str(asked["title"]),
                "due": str(asked["due"]),
                "estimate_min": int(asked["minutes"]),
                "revision": 0,
            }
        )
        self._window.session.save()
        self._settle()
        return {}

    def _block(self, asked: dict) -> dict:
        block = asked.get("block")
        if not isinstance(block, dict):
            raise StepRefused("a block is a JSON object")
        self._window.session.add_block(block)
        self._window.session.save()
        self._settle()
        return {}

    def _clock(self, asked: dict) -> dict:
        from backend.tests.fake_clock import CLOCK

        CLOCK.set(datetime.fromisoformat(str(asked["at"])))
        self._window._tick_material_clock()
        self._turns(10)
        return {}

    def _preferences(self, asked: dict) -> dict:
        values = asked.get("values")
        if not isinstance(values, dict):
            raise StepRefused("preferences are a JSON object")
        if "clock_24h" in values:
            from desktop.native.weekmodel import set_clock_24h

            set_clock_24h(bool(values["clock_24h"]))
        session = self._window.session
        session.preferences = {**(session.preferences or {}), **values}
        self._host().publish()
        self._turns(20)
        return {}

    def _open_day(self, asked: dict) -> dict:
        self._window.session.open_day(str(asked["day"]))
        self._host().bridge.showPage("day")
        self._turns(10)
        return {}

    def _reveal(self, asked: dict) -> dict:
        item = self._item(asked)
        flick = item.parentItem()
        while flick is not None and flick.property("contentHeight") is None:
            flick = flick.parentItem()
        if flick is None:
            raise StepRefused(f"{asked.get('target')} is not in a scrolling list")
        top = item.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y()
        limit = max(0.0, float(flick.property("contentHeight")) - float(flick.height()))
        flick.setProperty("contentY", min(max(0.0, top - 120), limit))
        self._turns(4)
        return {}

    def _set_property(self, asked: dict) -> dict:
        self._item(asked).setProperty(str(asked["name"]), asked.get("value"))
        self._turns(10)
        return {}


BLOCK_FIELDS = ("id", "title", "kind", "start", "duration_min", "days", "assignment_id", "pinned")


def _pair(value: object) -> tuple[int, int]:
    if value is None:
        return 0, 0
    if not (isinstance(value, list) and len(value) == 2):
        raise StepRefused("a move is [dx, dy]")
    return int(value[0]), int(value[1])


def _modifiers(held: str) -> Qt.KeyboardModifier:
    modifiers = Qt.KeyboardModifier.NoModifier
    for part in filter(None, held.split("+")):
        modifier = MODIFIERS.get(part.lower())
        if modifier is None:
            raise StepRefused(f"no modifier called {part!r}")
        modifiers |= modifier
    return modifiers


def _seen(item: QObject) -> dict:
    text = item.property("text")
    title = item.property("title")
    opacity = item.property("opacity")
    corner = item.mapToScene(QPointF(0, 0)) if hasattr(item, "mapToScene") else QPointF(0, 0)
    face = QAccessible.queryAccessibleInterface(item)
    return {
        "found": True,
        "name": str(item.objectName() or ""),
        "text": text if isinstance(text, str) else "",
        "title": title if isinstance(title, str) else "",
        "enabled": bool(item.isEnabled()) if hasattr(item, "isEnabled") else True,
        "focused": bool(item.property("activeFocus")),
        "visible": bool(item.isVisible()) if hasattr(item, "isVisible") else False,
        "opacity": float(opacity) if isinstance(opacity, (int, float)) else 1.0,
        "rect": [
            float(corner.x()),
            float(corner.y()),
            float(item.property("width") or 0),
            float(item.property("height") or 0),
        ],
        "accessible": face.text(QAccessible.Text.Name) if face is not None else "",
    }


def _ring_shown(item: QObject) -> bool:
    """The focus ring drawn on the item: a FocusRing child, or the item's own ringRadius ring, showing."""
    rings = [
        child
        for child in _visuals(item)
        if "FocusRing" in type(child).__name__ or child.property("ringRadius") is not None
    ]
    return any(
        ring.property("shown") is True
        or (ring.property("visible") is True and float(ring.property("opacity") or 0) > 0)
        for ring in rings
    )
