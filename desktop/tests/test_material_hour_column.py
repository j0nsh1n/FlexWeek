"""Material Week at a larger text size: the week shows the time now again after the rows grow.

Expected values come from the Week's own promise (it opens on the time now) and the account's clock,
held at Thursday 19:00, not from reading what the QML prints.
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_week"]

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import look_file  # noqa: E402
from desktop.tests.test_material_week import (  # noqa: E402
    NOW_MINUTE,
    _bridge,
    _named,
    _pref,
    _pump,
    _qml,
    _reset,
)


def _text_size(window: NativeWindow, scale: float) -> None:
    """Set Advanced > Text size the way the look file keeps it, and publish it."""
    path = look_file()
    stored = json.loads(path.read_text()) if path.exists() else {}
    material = stored.setdefault("material", {})
    material["advanced"] = {**material.get("advanced", {}), "scale": scale}
    path.write_text(json.dumps(stored))
    window._material_page.publish()
    _pump(QApplication.instance(), 6)


def test_a_larger_text_size_brings_the_time_now_back_into_view(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _reset(window, qapp)
    grid = _qml(root, "weekScroller")
    row_before = int(_bridge(window).property("hourRow"))
    # The student had scrolled up to the morning before changing the text size.
    grid.setProperty("contentY", 0.0)
    _pump(qapp, 4)
    try:
        _text_size(window, 1.5)
        row = int(_bridge(window).property("hourRow"))
        assert row > row_before, "the text size did not grow the rows, so this test would prove nothing"

        now_y = NOW_MINUTE / 60 * row
        top = float(grid.property("contentY"))
        assert top <= now_y <= top + float(grid.property("height"))
    finally:
        look_file().unlink(missing_ok=True)
        window._material_page.publish()
        _pump(qapp, 4)


def _cut_labels(root) -> list[str]:
    """Hour labels whose words are wider than the column they are drawn in, so the rail cuts their digits."""
    return [
        str(label.property("text"))
        for label in _named(root, "hourLabel")
        if float(label.property("contentWidth")) > float(label.property("width"))
    ]


def test_every_hour_label_fits_its_column_at_a_larger_text_size(
    qapp: QApplication, window: NativeWindow
) -> None:
    """V23/V28: at Large text "10:00 AM" lost its first digit under the rail. The column grows with the
    widest label, so no label is wider than its column, and at the normal size it stays 68 px."""
    root = _reset(window, qapp)
    # The 12-hour clock's labels are the widest the Week draws.
    _pref(window, clock_24h=False)
    window._material_page.publish()
    _pump(qapp)
    week = _qml(root, "materialWeek")
    assert any("AM" in str(label.property("text")) for label in _named(root, "hourLabel")), (
        "no 12-hour labels found, so this test would prove nothing"
    )
    assert int(week.property("gutter")) == 68
    assert _cut_labels(root) == []
    try:
        _text_size(window, 1.5)
        assert _cut_labels(root) == []
        assert int(week.property("gutter")) > 68
    finally:
        _pref(window, clock_24h=True)
        look_file().unlink(missing_ok=True)
        window._material_page.publish()
        _pump(qapp, 4)
