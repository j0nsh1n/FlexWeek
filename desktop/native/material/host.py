"""The Material page that sits in the window stack.

Qt Quick is imported here, not from the widgets window, and the scene-graph
handler is connected before the host is shown. A load or graphics failure is
reported; this page does not change the saved surface.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QEventLoop, Qt, QTimer, QUrl, Signal
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget

from desktop.native.look import design_look
from desktop.native.material.bridge import MaterialBridge
from desktop.native.material.theme import qml_dir, qml_path, register_fonts

log = logging.getLogger("flexweek.material")


class MaterialPage(QWidget):
    """One QQuickWidget. `load` is safe to call again after a failure."""

    failed = Signal(str)
    widgets_requested = Signal()

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.setObjectName("materialPage")
        self._window = window
        self._ready = False
        self._failed = False
        self.failure = ""
        self.break_load = False
        self.bridge = MaterialBridge(window)
        self.bridge.setParent(self)
        self.bridge.widgetsRequested.connect(self.widgets_requested)
        QQuickStyle.setStyle("Material")
        self._quick = QQuickWidget(self)
        self._quick.setObjectName("materialQuick")
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self._quick.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Connected before the host can be shown. Qt ends the process if a
        # scene-graph error has no slot.
        self._quick.sceneGraphError.connect(self._on_scene_graph_error)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self._quick)

    @property
    def root(self):
        return self._quick.rootObject()

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
        self._quick.engine().addImportPath(str(qml_dir()))
        # The root property has to exist before the shell is created, or every binding reads null.
        self._quick.setInitialProperties({"bridge": self.bridge})
        self._quick.setSource(QUrl.fromLocalFile(str(page)))
        if self._quick.status() == QQuickWidget.Status.Loading:
            loop = QEventLoop()
            self._quick.statusChanged.connect(loop.quit)
            self._quick.sceneGraphError.connect(loop.quit)
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
        if self._failed or self._quick.status() == QQuickWidget.Status.Error or self.root is None:
            self._failed = True
            self._ready = False
            if not self.failure:
                problems = "; ".join(error.toString() for error in self._quick.errors())
                self.failure = problems or "Material 3 could not load"
            log.warning("%s", self.failure)
            return False
        self._ready = True
        return True

    def publish(self) -> None:
        mode, contrast_name = appearance_of(self._window)
        self.bridge.set_appearance(mode, contrast_name)
        self.bridge.refresh()


def appearance_of(window: Any) -> tuple[str, str]:
    """Light or dark, and standard or high contrast, from the look the window wears."""
    pack, system_dark, accent = window._look_inputs()
    look = window._worn_look()
    palette, selected = design_look("your", pack, system_dark, look, accent)
    mode = "dark" if palette.get("axis") == "dark" else "light"
    custom = selected.get("custom") or {}
    base = custom.get("base", selected.get("preset"))
    contrast_name = "high" if base == "high-contrast" else "std"
    return mode, contrast_name
