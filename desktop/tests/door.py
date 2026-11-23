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
  property {target, name}   {value}: one property of the item, as JSON (text for anything else)
  pump {turns}              let the window run that many turns of its event loop
  app                       {week_start, selected_month, screen}: what the session holds (the Python host's
                            stand-in for the view state the Rust core will expose)
  slot_error                a slot that raises on the next turn of the event loop (the door's own test of
                            the report below)
A target is {"name": objectName} or {"words": the text a student reads}, optionally with "within": the
objectName of the item to look inside (the "20" in the date picker's month, not another "20"). Names are
looked for among painted items first, so a Repeater's rows are found too.

An error raised inside a Qt slot, at start or while the app ran between steps or during one, fails the next
step's answer, as the Python suite fails a test on one; it is also printed, so it is never lost.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
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
            "pump": self._pump,
            "app": self._app,
            "slot_error": self._slot_error,
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

    def _find(self, target: object) -> QObject | None:
        if not isinstance(target, dict):
            raise StepRefused("a target is a JSON object")
        root = self._host().rootObject()
        if root is None:
            return None
        if "within" in target:
            root = _named(root, str(target["within"]))
            if root is None:
                return None
        if "name" in target:
            return _named(root, str(target["name"]))
        if "words" not in target:
            raise StepRefused("a target names an item or its words")
        words = str(target["words"])
        for item in _visuals(root):
            text = item.property("text")
            if isinstance(text, str) and text == words and item.isVisible():
                return item
        return None

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
        modifiers = Qt.KeyboardModifier.NoModifier
        for part in held:
            modifier = MODIFIERS.get(part.lower())
            if modifier is None:
                raise StepRefused(f"no modifier called {part!r}")
            modifiers |= modifier
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
        text = item.property("text")
        return {
            "found": True,
            "name": str(item.objectName() or ""),
            "text": text if isinstance(text, str) else "",
            "enabled": bool(item.isEnabled()) if hasattr(item, "isEnabled") else True,
            "focused": bool(item.property("activeFocus")),
            "visible": bool(item.isVisible()) if hasattr(item, "isVisible") else False,
        }

    def _property(self, asked: dict) -> dict:
        value = self._item(asked).property(str(asked["name"]))
        if isinstance(value, float) and not math.isfinite(value):
            return {"value": str(value)}
        return {"value": value if isinstance(value, PLAIN) else str(value)}

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
        return {
            "week_start": session.week_start,
            "selected_month": session.selected_month,
            "screen": str(bridge.screen),
        }
