"""What the window-chrome screens (desktop/tests/pictures/_*_g14.py) share: a week with school in it, a view
shown, a text size set. Preparing a picture never asserts."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QApplication

from desktop.native.layouts.registry import LAYOUTS
from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.waiting import wait_until

# The Widgets designs the Week is drawn in; Material has a shell of its own.
WIDGETS_DESIGNS = tuple(name for name, spec in LAYOUTS.items() if spec.role == "plan")

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 405,
    "days": [0, 1, 2, 3, 4],
}


def idle(window: NativeWindow) -> None:
    wait_until(None, lambda: not window.session.busy and not window.session.dirty)


def pump(count: int = 4) -> None:
    for _ in range(count):
        QApplication.processEvents()


def show_view(window: NativeWindow, view: str) -> None:
    """`view` of a week with school in it: an empty week shows its welcome instead of the hours."""
    if not window.session.blocks:
        window.session.add_block(SCHOOL)
        window.session.save()
        idle(window)
    window.findChild(QAbstractButton, f"view{view.title()}").click()
    wait_until(None, lambda: not window.session.busy)
    pump(3)


def text_size(window: NativeWindow, size: str) -> None:
    window._look = sanitize_look({**window._look, "knobs": {**window._look.get("knobs", {}), "text": size}})
    window._apply_appearance()
