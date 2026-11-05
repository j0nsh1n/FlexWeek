"""PR 6 polish: Month chips without purple, Widgets styles as a text button.

Expected colours and kinds come from the B3a3 theme keys (classes.assignments,
statusOverdue / statusOverdueTint) and from the Look page's one-filled-button rule,
not from what the QML currently paints.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from desktop.native.material.theme import scheme, theme_object

QML = Path(__file__).resolve().parents[1] / "native" / "material" / "qml"
LOOK = QML / "settings" / "LookSection.qml"
PURPLE_FAMILY = {"#eae6fa", "#2a244d", "#7c6cd6", "#9b8cf0", "#fad8fd", "#705574"}
# QML engine/component/item form a cycle; keep them so the collector fixture does not see them.
_HOLD: list[object] = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["test-pr6-polish"])


@pytest.fixture
def cell(qapp: QGuiApplication) -> Iterator[QQuickItem]:
    engine = QQmlEngine()
    engine.addImportPath(str(QML))
    comp = QQmlComponent(engine)
    source = 'import month 1.0\nMonthCell { width: 180; height: 110; iso: "2026-11-08"; day: 8 }\n'
    comp.setData(source.encode(), engine.baseUrl())
    assert comp.isReady(), comp.errorString()
    item = comp.create()
    assert item is not None
    _HOLD.extend((engine, comp, item))
    yield item


def _hex(value: object) -> str:
    return QColor(value).name().lower()


def _walk(item: QQuickItem) -> Iterator[QQuickItem]:
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _find(item: QQuickItem, name: str) -> QQuickItem | None:
    for node in _walk(item):
        if node.objectName() == name:
            return node
    return None


def _show(cell: QQuickItem, theme: dict, chips: list[dict]) -> None:
    cell.setProperty("theme", theme)
    cell.setProperty("chipsJson", json.dumps(chips))
    QGuiApplication.processEvents()


def test_due_and_overdue_month_chips_use_class_and_status_colours_with_icons(
    qapp: QGuiApplication, cell: QQuickItem
) -> None:
    """Due chips wear homework class fill/ink plus edit_note; overdue wear overdue tint/ink plus warning."""
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        homework = th["classes"]["assignments"]
        for kind, fill, ink, icon in (
            ("due", homework["fill"], homework["ink"], "edit_note"),
            ("overdue", th["statusOverdueTint"], th["statusOverdue"], "warning"),
        ):
            _show(cell, th, [{"kind": kind, "text": f"{kind} History essay"}])
            chip = _find(cell, "monthChip")
            text = _find(cell, "monthChipText")
            mark = _find(cell, "monthChipIcon")
            bar = _find(cell, "monthChipBar")
            assert chip is not None and text is not None
            assert chip.property("radius") == pytest.approx(chip.property("height") / 2)
            assert _hex(chip.property("color")) == fill.lower(), f"{kind} fill in {mode}"
            assert _hex(text.property("color")) == ink.lower(), f"{kind} ink in {mode}"
            assert mark is not None and mark.property("visible") is True
            assert mark.property("name") == icon
            assert _hex(text.property("color")) != "#ffffff"
            assert _hex(text.property("color")) != homework["bar"].lower()
            assert _hex(chip.property("color")) not in PURPLE_FAMILY
            assert _hex(chip.property("color")) != _hex(th["tertiaryContainer"])
            if kind == "due":
                assert bar is not None and bar.property("visible") is True
                assert _hex(bar.property("color")) == homework["bar"].lower()
            else:
                assert bar is None or bar.property("visible") is False


def test_narrow_month_dots_use_the_chip_colours(qapp: QGuiApplication, cell: QQuickItem) -> None:
    """At phone width a day shows dots, not chips: due is homework's bar, overdue the overdue
    status, and no purple."""
    try:
        cell.setProperty("narrow", True)
        for mode in ("light", "dark"):
            th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
            homework = th["classes"]["assignments"]["bar"]
            for kind, colour in (("due", homework), ("overdue", th["statusOverdue"])):
                _show(cell, th, [{"kind": kind, "text": f"{kind} History essay"}])
                dot = _find(cell, "monthDot")
                assert dot is not None, f"{kind} dot in {mode}"
                assert _hex(dot.property("color")) == colour.lower(), f"{kind} dot in {mode}"
                assert _hex(dot.property("color")) not in PURPLE_FAMILY
    finally:
        cell.setProperty("narrow", False)
        QGuiApplication.processEvents()


def test_a_plain_month_chip_stays_neutral(qapp: QGuiApplication, cell: QQuickItem) -> None:
    """A planned-time chip keeps the muted surface, no status icon, and a pill radius."""
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        _show(cell, th, [{"kind": "plain", "text": "8:00 AM School"}])
        chip = _find(cell, "monthChip")
        text = _find(cell, "monthChipText")
        mark = _find(cell, "monthChipIcon")
        bar = _find(cell, "monthChipBar")
        assert chip is not None and text is not None
        assert chip.property("radius") == pytest.approx(chip.property("height") / 2)
        assert _hex(chip.property("color")) == _hex(th["surfaceContainerHighest"])
        assert _hex(text.property("color")) == _hex(th["inkMuted"])
        assert mark is None or mark.property("visible") is False or mark.property("name") == ""
        assert bar is None or bar.property("visible") is False


def test_widgets_styles_is_a_text_button_and_look_has_at_most_one_filled() -> None:
    """Look's Widgets styles control is kind text; the Look page keeps at most one filled button."""
    look_text = LOOK.read_text(encoding="utf-8")
    use = re.search(
        r'objectName:\s*"useWidgets"[\s\S]*?kind:\s*"([^"]+)"',
        look_text,
    )
    assert use is not None
    assert use.group(1) == "text"
    filled = re.findall(r'kind:\s*"filled"', look_text)
    assert len(filled) <= 1
