"""Keyboard or pointer: what the last input was, for Material's focus rings.

Qt Quick has no :focus-visible. The rings read the FocusVisible singleton; one filter on the application
keeps it true after a key and false after a mouse, touch or tablet press, for every engine that asked.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine
from shiboken6 import isValid

# A key bound to a Shortcut (Esc, the number keys) arrives as ShortcutOverride and Shortcut, not KeyPress.
_KEYS = {QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride, QEvent.Type.Shortcut}
_POINTERS = {
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonDblClick,
    QEvent.Type.TouchBegin,
    QEvent.Type.TabletPress,
}


class InputModality(QObject):
    """Sets `keyboard` on each FocusVisible it was given. It belongs to the application, so it outlives
    every engine; a singleton whose engine is gone is dropped."""

    def __init__(self, app: QGuiApplication) -> None:
        super().__init__(app)
        self._targets: list[QObject] = []

    def add(self, singleton: QObject) -> None:
        if all(target is not singleton for target in self._targets):
            self._targets.append(singleton)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt virtual
        kind = event.type()
        if kind in _KEYS:
            keyboard = True
        elif kind in _POINTERS:
            keyboard = False
        else:
            return False
        self._targets = [target for target in self._targets if isValid(target)]
        for target in self._targets:
            target.setProperty("keyboard", keyboard)
        return False


_watcher: InputModality | None = None


def install(engine: QQmlEngine) -> InputModality | None:
    """Watch the app's input for this engine's rings. None when there is no app or no components module."""
    global _watcher
    app = QGuiApplication.instance()
    singleton = engine.singletonInstance("components", "FocusVisible")
    if app is None or singleton is None:
        return None
    if _watcher is None or not isValid(_watcher):
        _watcher = InputModality(app)
        app.installEventFilter(_watcher)
    _watcher.add(singleton)
    return _watcher
