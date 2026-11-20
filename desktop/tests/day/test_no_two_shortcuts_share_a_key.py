# ruff: noqa: F811
"""In Material's own window every QML Shortcut can match (in the old widget host a window shortcut never
did), and when two enabled shortcuts share a key Qt runs neither and swallows the key: Esc stopped cancelling
a Week range drag that way (step 11, 2026-11-20). In each state a student is often in, no key may belong to
two enabled shortcuts."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401


def _keys(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [key for part in value for key in _keys(part)]
    if isinstance(value, int):
        return [seq.toString() for seq in QKeySequence.keyBindings(QKeySequence.StandardKey(value))]
    text = QKeySequence(value).toString() if value is not None else ""
    return [text] if text else []


def _clashes(root: QObject) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    found = root.findChildren(QObject)
    shortcuts = [item for item in found if item.metaObject().className().startswith("QQuickShortcut")]
    assert len(shortcuts) > 10, "the walk found no shortcuts, so it checks nothing"
    for item in shortcuts:
        if not item.property("enabled"):
            continue
        parent = item.parent()
        where = "-" if parent is None else f"{parent.metaObject().className()}#{parent.objectName() or '-'}"
        keys = _keys(item.property("sequence")) + _keys(item.property("sequences"))
        for key in dict.fromkeys(keys):
            owners.setdefault(key, []).append(where)
    return {key: who for key, who in owners.items() if len(who) > 1}


def _no_clash(qapp: QApplication, window: NativeWindow, state: str) -> None:
    pump(qapp, 10)
    clashes = _clashes(window._material_page.root)
    assert clashes == {}, f"{state}: keys with two enabled shortcuts {clashes}"


def test_no_key_has_two_enabled_shortcuts_on_the_main_screens(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    bridge = window._material_page.bridge
    for page in ("week", "day", "month", "myday", "settings"):
        bridge.showPage(page)
        _no_clash(qapp, window, page)
    bridge.showPage("week")
    bridge.sheets.openHelp()
    _no_clash(qapp, window, "Help open")
    bridge.sheets.closeSheet()
    week = qml(root, "materialWeek")
    week.setProperty("dragRangeActive", True)
    bridge.sheets.setDragRangeActive(True)
    _no_clash(qapp, window, "a range drag on the Week")
    bridge.sheets.setDragRangeActive(False)
    week.setProperty("dragRangeActive", False)
