"""Material's own Qt Quick window.

Qt Quick is imported here, not from the widgets window, and the scene-graph
handler is connected before the host is shown. A load or graphics failure is
reported; this window does not change the saved surface. A QQuickView paces its
frames to the screen, which the QQuickWidget it replaced could not.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle

from desktop.native.material.bridge import MaterialBridge
from desktop.native.material.focus_visible import install as install_focus_visible
from desktop.native.material.theme import (
    mode_of,
    qml_dir,
    qml_path,
    read_material_choice,
    register_fonts,
    resolved_mode,
)

log = logging.getLogger("flexweek.material")


class MaterialPage(QQuickView):
    """Material's window. `load` is safe to call again after a failure."""

    failed = Signal(str)

    def __init__(self, window: QObject) -> None:
        # Qt refuses a style change once components have loaded, so a second window leaves it alone.
        if QQuickStyle.name() != "Material":
            QQuickStyle.setStyle("Material")
        super().__init__()
        self.setObjectName("materialPage")
        self._window = window
        self._ready = False
        self._failed = False
        self.failure = ""
        self.break_load = False
        # The bridge stays the controller's child, so the controller finds and disposes it.
        self.bridge = MaterialBridge(window)
        self.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        # Connected before the window can be shown. Qt ends the process if a
        # scene-graph error has no slot.
        self.sceneGraphError.connect(self._on_scene_graph_error)

    @property
    def root(self):
        return self.rootObject()

    def _on_scene_graph_error(self, _error: object, message: object) -> None:
        self._failed = True
        self._ready = False
        self.failure = str(message)
        log.warning("Material scene graph failed: %s", message)
        self.failed.emit(self.failure)

    def load(self) -> bool:
        """Load the shell. False leaves the saved surface alone for the window to keep."""
        if self.break_load:
            self._failed = True
            self._ready = False
            self.failure = "Material 3 could not load"
            log.warning("%s", self.failure)
            return False
        if self._ready and not self._failed and self.root is not None:
            return True
        self._failed = False
        self.failure = ""
        page = qml_path()
        if not page.is_file():
            self._failed = True
            self._ready = False
            self.failure = f"Material 3 could not load {page}"
            log.warning("%s", self.failure)
            return False
        # Faces and the component import have to be in place before the shell is created.
        register_fonts()
        self.engine().addImportPath(str(qml_dir()))
        # The root property has to exist before the shell is created, or every binding reads null.
        self.setInitialProperties({"bridge": self.bridge})
        self.setSource(QUrl.fromLocalFile(str(page)))
        if self.status() == QQuickView.Status.Loading:
            loop = QEventLoop()
            self.statusChanged.connect(loop.quit)
            self.sceneGraphError.connect(loop.quit)
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
        if self._failed or self.status() == QQuickView.Status.Error or self.root is None:
            self._failed = True
            self._ready = False
            if not self.failure:
                problems = "; ".join(error.toString() for error in self.errors())
                self.failure = problems or "Material 3 could not load"
            log.warning("%s", self.failure)
            return False
        install_focus_visible(self.engine())
        self._ready = True
        return True

    def publish(self) -> None:
        mode, contrast_name = appearance_of(self._window)
        self.bridge.set_appearance(mode, contrast_name)
        self.bridge.refresh()


def device_is_dark() -> bool:
    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


def appearance_of(window: Any) -> tuple[str, str]:
    """Light or dark, and standard or high contrast, from Material's own saved choice.

    System follows the device; Light and Dark win over it. Nobody signed in follows the device's light
    or dark but keeps the contrast last chosen on this computer (the look file is the computer's, not
    the account's), so a student who needs High contrast still has it on the sign-in screens. The
    Widgets look and the account's theme pack play no part.
    """
    dark = device_is_dark()
    try:
        stored = json.loads(window._look_path().read_text(encoding="utf-8"))
    except OSError, ValueError:
        stored = None
    choice = read_material_choice(stored)
    if window._wears_carried_look():
        return resolved_mode("system", dark), choice["contrast"]
    return mode_of(choice, dark), choice["contrast"]
