"""Shared set-up for the Retro desktop's tests: the view shown on its own at a fixed size, with the
scene it is given, and lookups of its windows and taskbar. Not a test module."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QWidget,
)

from desktop.native.layouts.base import Scene  # noqa: E402
from desktop.native.layouts.registry import LEGACY_COLOURS, options_for, tokens_for  # noqa: E402
from desktop.native.layouts.retro import RetroView  # noqa: E402
from desktop.native.look import design_look, resolved_palette  # noqa: E402
from desktop.native.weekmodel import build_week, minute_of  # noqa: E402
from desktop.tests.test_weekmodel import BLOCKS, HOMEWORK, TRACE, WEEK  # noqa: E402

NBSP = " "


def palette_of(look: str = "light") -> dict:
    if look.startswith("pack:") or look.startswith("preset:"):
        return design_look(look, "system", False, None)[0]
    return {
        "light": resolved_palette("light-frost", False, None, "default"),
        "dark": resolved_palette("dark-frost", True, None, "default"),
        "contrast": resolved_palette("system", False, {"preset": "high-contrast", "knobs": {}}, "default"),
    }[look]


def scene(
    clock: str = "13:40",
    blocks: list[dict] | None = None,
    *,
    surface: str = "week",
    iso_day: str = "",
    scale: float = 1.0,
    look: str = "light",
    **chosen: str,
) -> Scene:
    if "colour" in chosen:
        chosen["look"] = LEGACY_COLOURS["retro"].get(chosen.pop("colour"), "your")
    options = {**options_for(None, "retro"), **chosen}
    week = build_week(WEEK, blocks or BLOCKS, HOMEWORK, TRACE)
    page_palette = palette_of(look)
    if options["look"] != "your":
        page_palette, _active = design_look(
            options["look"], "system", page_palette.get("axis") == "dark", None, page_palette["accent"]
        )
    return Scene(
        week,
        3,
        minute_of(clock),
        options,
        tokens_for("retro", options["look"], page_palette),
        scale=scale,
        surface=surface,
        iso_day=iso_day,
    )


def shown(
    qapp: QApplication,
    width: int = 1366,
    height: int = 720,
    blocks: list[dict] | None = None,
    **chosen: str,
) -> RetroView:
    view = RetroView()
    view.resize(width, height)
    view.show_week(scene(blocks=blocks, **chosen))
    view.show()
    qapp.processEvents()
    return view


def windows(view: RetroView) -> list[str]:
    """The windows open on the desktop. A closed one is kept, hidden, so it opens where it was."""
    return sorted(
        item.objectName()
        for item in view.findChildren(QFrame)
        if item.property("role") == "window" and item.isVisibleTo(view)
    )


def task(view: RetroView, key: str) -> QPushButton:
    return view.findChild(QPushButton, f"retroTask-{key}")


def text(view: RetroView, name: str) -> str:
    return view.findChild(QLabel, name).text()


def item_holding(layout: QLayout, widget: QWidget) -> QLayoutItem | None:
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            return item
        inner = item.layout()
        if inner is not None and (found := item_holding(inner, widget)) is not None:
            return found
    return None
