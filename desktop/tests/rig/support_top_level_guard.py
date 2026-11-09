"""A watcher for widgets that become windows of their own, shared by the tests that drive a whole
session (light app and e2e)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QMenu, QWidget

from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 405,
    "days": [0, 1, 2, 3, 4],
}


class TopLevelShowGuard(QObject):
    """Record any shown window that is not an expected app surface."""

    def __init__(self, main: NativeWindow) -> None:
        super().__init__()
        self.main = main
        self.shown: list[str] = []
        self.offscreen: list[str] = []
        self.unexpected: list[str] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
            description = (
                f"{type(watched).__name__}#{watched.objectName()} "
                f"title={watched.windowTitle()!r} type={watched.windowType()}"
            )
            self.shown.append(description)
            if watched.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):
                # Design previews receive Show to render a picture, while Qt keeps them offscreen.
                self.offscreen.append(description)
                return False
            allowed_types = {
                Qt.WindowType.Dialog,
                Qt.WindowType.Popup,
                Qt.WindowType.ToolTip,
                Qt.WindowType.Sheet,
            }
            if (
                watched is not self.main
                and not isinstance(watched, (QDialog, QMenu))
                and watched.windowType() not in allowed_types
            ):
                self.unexpected.append(description)
        return False


def prove_the_guard_sees_a_window(qapp: QApplication, guard: TopLevelShowGuard) -> None:
    """The filter must see a window being shown. What the session itself shows depends on what earlier
    tests in this process left cached (design pictures are drawn once), so it is proved here with a
    dialog of its own, which is an allowed kind."""
    probe = QDialog()
    probe.setObjectName("guardProbe")
    probe.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    probe.show()
    qapp.processEvents()
    probe.hide()
    probe.deleteLater()
    assert any("#guardProbe " in line for line in guard.shown), "the app-wide filter saw no Show"


def show_view(qapp: QApplication, window: NativeWindow, view: str) -> None:
    """`view` of a week with school in it: an empty week shows its welcome instead of the hours."""
    if not window.session.blocks:
        window.session.add_block(SCHOOL)
        window.session.save()
        wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    button = window.findChild(QAbstractButton, f"view{view.title()}")
    assert button is not None, f"view{view.title()} is not available"
    button.click()
    wait_until(qapp, lambda: not window.session.busy)
    for _ in range(3):
        qapp.processEvents()
