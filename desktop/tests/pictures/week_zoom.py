"""Pictures of the hours' zoom: the Material week one zoom step in. The renderer gathers this module's
SCREENS. The Widgets week's zoom pictures went with the Widgets week (step 9, group 5b3)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.week.support_zoom import block_named, bridge_of, pump, show_material


def _app() -> QApplication:
    app = QApplication.instance()
    assert app is not None
    return app


def _material_clinic_at_ten(window: NativeWindow) -> None:
    app = _app()
    session = window.session
    session.add_block(
        {
            "id": "clinic",
            "title": "Clinic",
            "kind": "locked",
            "category": "activity",
            "start": "10:00",
            "duration_min": 60,
            "days": [5],
        }
    )
    session.save()
    root = show_material(app, window)
    window._zoom.pop("material.week", None)
    window._material_page.publish()
    pump(app)
    # One step in from the standard row, so the picture shows the zoomed grid.
    bridge_of(window).zoomBy(1)
    pump(app)
    assert block_named(root, "Clinic") is not None


SCREENS: list[Screen] = [
    Screen(
        id="week.material-week-rows-follow-zoom",
        area="week",
        prepare=_material_clinic_at_ten,
        checks=(
            "Material week, one zoom step in from standard (72 px an hour): Clinic, which starts at "
            "10:00, sits 10 hour rows (720 px) from the top of the grid; at the standard row (56 px) "
            "it sits 560 px down. Blocks line up with the hour lines at both zoom levels."
        ),
        sources=("desktop/native/material", "desktop/native/window.py"),
    ),
]
