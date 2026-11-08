"""Material's Month dates each carry the shared focus ring. What the ring looks like (radius 14, the theme's
primary colour) is a picture (desktop/tests/pictures/_month_g14.py, month.date_cell_ring)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import pump, visuals
from desktop.tests.week.support_material_page import fresh_material


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-month-date-ring"])


def test_month_date_cells_use_the_shared_ring(qapp: QApplication, window: NativeWindow) -> None:
    root = fresh_material(qapp, window)
    window._material_page.bridge.showPage("month")
    pump(qapp, 10)

    cells = [
        item for item in visuals(root) if item.objectName() and item.objectName().startswith("monthDate-")
    ]
    assert len(cells) > 0
    for cell in cells:
        rings = [
            child
            for child in visuals(cell)
            if "FocusRing" in type(child).__name__
            or (hasattr(child, "property") and child.property("ringRadius") is not None)
        ]
        assert rings, f"{cell.objectName()} has no focus ring"
