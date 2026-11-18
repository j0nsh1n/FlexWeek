"""Raising every Material prompt on a real window, at a text size and size of window, and reading where its
buttons sit. The prompt walk test and the B2 dialog tests share these."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import QObject, QPointF, QRectF
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import named, pump, visuals
from desktop.tests.sheets.support_material_pictures import seed_school_and_essay
from desktop.tests.sheets.support_material_sheets import bridge, material_week
from desktop.tests.window_support import look_file

SCALES = {"Normal": 1.0, "Large": 1.3}


def set_look(window: NativeWindow, *, mode: str, scale: float) -> None:
    path = look_file()
    stored = json.loads(path.read_text()) if path.exists() else {}
    material = stored.setdefault("material", {})
    material["mode"] = mode
    material["advanced"] = {**material.get("advanced", {}), "scale": scale}
    path.write_text(json.dumps(stored))
    window._material_page.publish()
    pump(QApplication.instance(), 10)


@contextmanager
def looked(window: NativeWindow, *, mode: str, scale: float, size: tuple[int, int]) -> Iterator[None]:
    path = look_file()
    before = path.read_text() if path.exists() else None
    window.resize(*size)
    set_look(window, mode=mode, scale=scale)
    try:
        yield
    finally:
        if before is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(before)
        window._material_page.publish()
        pump(QApplication.instance(), 5)


def week_with_school(qapp: QApplication, window: NativeWindow) -> QObject:
    root = material_week(qapp, window)
    seed_school_and_essay(window)
    pump(qapp, 20)
    return root


def prompt_item(window: NativeWindow) -> QObject | None:
    root = window._material_page.root
    shown = [item for item in named(root, "sheetPrompt") if item.property("visible")]
    return shown[0] if shown else None


def card_of(prompt: QObject) -> QObject:
    return named(prompt, "sheetCard")[0]


def rect_in_scene(item: QObject) -> QRectF:
    top = item.mapToScene(QPointF(0, 0))
    return QRectF(top.x(), top.y(), item.width(), item.height())


def footer_buttons(prompt: QObject) -> list[QObject]:
    return [
        item
        for item in visuals(prompt)
        if str(item.objectName()).startswith("prompt_")
        and not str(item.objectName()).startswith("prompt_card_")
    ]


def buttons_outside_card(prompt: QObject) -> list[str]:
    """The names of footer buttons that are not wholly inside the dialog's card."""
    card = rect_in_scene(card_of(prompt))
    outside = []
    for item in footer_buttons(prompt):
        box = rect_in_scene(item)
        if (
            box.left() < card.left() - 0.5
            or box.right() > card.right() + 0.5
            or box.top() < card.top() - 0.5
            or box.bottom() > card.bottom() + 0.5
        ):
            outside.append(str(item.objectName()))
    return outside


def grab(window: NativeWindow, path: str) -> None:
    quick = window._material_page._quick
    pump(QApplication.instance(), 30)
    quick.grabFramebuffer().save(path)


def bridge_sheets(window: NativeWindow):
    return bridge(window).sheets
