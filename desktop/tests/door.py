"""The test door (2.0.0 plan, P3): the Python app, started for tests, answers a screen test's steps over a
local socket file, so a screen test written in Rust (flexweek-testkit's Door) can run against the app that is
known to work. One JSON object per line each way. Test-only; it goes with the Python host.

Steps (each answers {"ok": true, ...} or {"ok": false, "error": "..."}):
  click {target}            a left click at the middle of the item, as the pointer does it
  key {key}                 a key press in the window: a Qt key name without "Key_" ("Return", "Down")
  type {text}               the text typed into the item that has the keyboard
  focus {target}            give the item the keyboard, where a test starts keys from
  read {target}             {found, name, text, enabled, focused, visible}
  property {target, name}   {value}: one property of the item, as JSON
  pump {turns}              let the window run that many turns of its event loop
  app                       {week_start, selected_month, screen}: what the session holds (the Python host's
                            stand-in for the view state the Rust core will expose)
A target is {"name": objectName} or {"words": the text a student reads}, optionally with "within": the
objectName of the item to look inside (the "20" in the date picker's month, not another "20").
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow

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


class Door(QObject):
    """Answers one test at a time on `path`, on the window's thread."""

    def __init__(self, window: NativeWindow, path: str) -> None:
        super().__init__(window)
        self._window = window
        self._buffer = b""
        self._socket: QLocalSocket | None = None
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
        }

    def _accept(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        self._socket = socket
        socket.readyRead.connect(self._incoming)

    def _incoming(self) -> None:
        socket = self._socket
        if socket is None:
            return
        self._buffer += bytes(socket.readAll().data())
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            answer = self._answer(line)
            socket.write(json.dumps(answer).encode() + b"\n")
            socket.flush()

    def _answer(self, line: bytes) -> dict:
        try:
            asked = json.loads(line)
            step = self._steps.get(asked.get("step", ""))
            if step is None:
                raise StepRefused(f"no step called {asked.get('step')!r}")
            return {"ok": True, **step(asked)}
        except (StepRefused, ValueError, KeyError) as error:
            return {"ok": False, "error": str(error)}

    # The window's parts.

    def _quick(self) -> Any:
        page = self._window._material_page
        if page is None:
            raise StepRefused("the Material window is not built")
        return page

    def _find(self, target: dict) -> QObject | None:
        root = self._quick().rootObject()
        if root is None:
            return None
        if "within" in target:
            root = root.findChild(QObject, str(target["within"]))
            if root is None:
                return None
        if "name" in target:
            return root.findChild(QObject, str(target["name"]))
        words = str(target.get("words", ""))
        for item in _visuals(root):
            text = item.property("text")
            if isinstance(text, str) and text == words and item.isVisible():
                return item
        return None

    def _item(self, asked: dict) -> QObject:
        item = self._find(asked.get("target") or {})
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
        spot = item.mapToScene(item.boundingRect().center())
        QTest.mouseClick(self._quick(), Qt.MouseButton.LeftButton, pos=QPoint(int(spot.x()), int(spot.y())))
        self._turns(10)
        return {}

    def _key(self, asked: dict) -> dict:
        key = getattr(Qt.Key, f"Key_{asked['key']}", None)
        if key is None:
            raise StepRefused(f"no key called {asked['key']!r}")
        QTest.keyClick(self._quick(), key)
        self._turns(10)
        return {}

    def _type(self, asked: dict) -> dict:
        QTest.keyClicks(self._quick(), str(asked["text"]))
        self._turns(10)
        return {}

    def _focus(self, asked: dict) -> dict:
        self._item(asked).forceActiveFocus()
        self._turns(5)
        return {}

    def _read(self, asked: dict) -> dict:
        item = self._find(asked.get("target") or {})
        if item is None:
            return {"found": False}
        text = item.property("text")
        return {
            "found": True,
            "name": str(item.objectName() or ""),
            "text": text if isinstance(text, str) else "",
            "enabled": bool(item.isEnabled()),
            "focused": bool(item.property("activeFocus")),
            "visible": bool(item.isVisible()),
        }

    def _property(self, asked: dict) -> dict:
        value = self._item(asked).property(str(asked["name"]))
        return {"value": value if isinstance(value, PLAIN) else str(value)}

    def _pump(self, asked: dict) -> dict:
        self._turns(int(asked.get("turns", 10)))
        return {}

    def _app(self, _asked: dict) -> dict:
        session = self._window.session
        bridge = self._quick().bridge
        return {
            "week_start": session.week_start,
            "selected_month": session.selected_month,
            "screen": str(bridge.screen),
        }
