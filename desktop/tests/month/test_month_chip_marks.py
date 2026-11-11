"""A Material month chip says what it is in an icon, not in colour alone: a due chip has the edit icon, an
overdue chip the warning icon, a planned time neither. Every chip has the left strip of its category
(tests/month/test_month_entries_carry_the_accent_strip.py compares the colour with Week's); a narrow day
shows a dot for each kind instead of chips.

How the chips and dots are coloured, and how they fade outside the month or sit on a picked date, is
judged on the pictures (screens `month.material_month_chips` and `month.material_month_dots_phone`).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from desktop.native.material.theme import scheme, theme_object  # noqa: E402

QML = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"
# QML engine/component/item form a cycle; keep them so the collector fixture does not see them.
_HOLD: list[object] = []


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["flexweek-month-chip-marks"])


@pytest.fixture
def cell(qapp: QGuiApplication) -> QQuickItem:
    engine = QQmlEngine()
    engine.addImportPath(str(QML))
    component = QQmlComponent(engine)
    source = 'import month 1.0\nMonthCell { width: 180; height: 110; iso: "2026-11-08"; day: 8 }\n'
    component.setData(source.encode(), engine.baseUrl())
    assert component.isReady(), component.errorString()
    item = component.create()
    assert item is not None
    _HOLD.extend((engine, component, item))
    return item


def _walk(item: QQuickItem) -> Iterator[QQuickItem]:
    yield item
    for child in item.childItems():
        yield from _walk(child)


def _find(item: QQuickItem, name: str) -> QQuickItem | None:
    for node in _walk(item):
        if node.objectName() == name:
            return node
    return None


def _show(cell: QQuickItem, chips: list[dict]) -> None:
    theme = theme_object(scheme("Slate", "light", "std"), "comfortable", False, False)
    cell.setProperty("theme", theme)
    cell.setProperty("chipsJson", json.dumps(chips))
    QGuiApplication.processEvents()


def test_due_and_overdue_month_chips_carry_their_icon_and_words(cell: QQuickItem) -> None:
    for kind, icon in (("due", "edit_note"), ("overdue", "warning")):
        _show(cell, [{"kind": kind, "text": f"{kind} History essay"}])
        text = _find(cell, "monthChipText")
        mark = _find(cell, "monthChipIcon")
        bar = _find(cell, "monthChipBar")
        assert text is not None and text.property("text") == f"{kind} History essay"
        assert mark is not None and mark.property("visible") is True
        assert mark.property("name") == icon
        assert bar is not None and bar.property("visible") is True


def test_a_plain_month_chip_has_no_status_icon_but_has_its_strip(cell: QQuickItem) -> None:
    _show(cell, [{"kind": "plain", "text": "8:00 AM School"}])
    text = _find(cell, "monthChipText")
    mark = _find(cell, "monthChipIcon")
    bar = _find(cell, "monthChipBar")
    assert text is not None and text.property("text") == "8:00 AM School"
    assert mark is None or mark.property("visible") is False or mark.property("name") == ""
    assert bar is not None and bar.property("visible") is True


def test_a_narrow_month_day_shows_a_dot_for_each_kind_of_chip(cell: QQuickItem) -> None:
    cell.setProperty("narrow", True)
    for kind in ("due", "overdue"):
        _show(cell, [{"kind": kind, "text": f"{kind} History essay"}])
        dot = _find(cell, "monthDot")
        assert dot is not None, f"{kind} dot"
