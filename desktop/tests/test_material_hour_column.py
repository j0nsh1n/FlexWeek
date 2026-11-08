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
from desktop.tests.test_material_week import NOW_MINUTE, _bridge, _pump, _qml, _reset  # noqa: E402


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
