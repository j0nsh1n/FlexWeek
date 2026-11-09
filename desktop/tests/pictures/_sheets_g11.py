"""Pictures of the shared Material 3 controls (the component gallery in desktop/native/material/qml/
components/Gallery.qml): what the old size, radius and colour checks of the component tests looked at.
(A fragment: the lead gathers these into screens_sheets.py.)"""

from __future__ import annotations

from desktop.tests.pictures.screen import Screen

SOURCES = (
    "desktop/native/material/qml/components",
    "desktop/native/material/theme.py",
)


def _gallery(window: object, *, scheme: str = "light", outlined: bool = False) -> object:
    from pathlib import Path

    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtWidgets import QApplication

    from desktop.tests.material_support import pump

    qml_folder = Path(__file__).resolve().parents[2] / "native" / "material" / "qml"
    widget = QQuickWidget(window)
    widget.engine().addImportPath(str(qml_folder))
    widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    widget.setSource(QUrl.fromLocalFile(str(qml_folder / "components" / "Gallery.qml")))
    widget.resize(1100, 1500)
    widget.show()
    root = widget.rootObject()
    root.setProperty("reduceMotion", True)
    root.setProperty("scheme", scheme)
    if outlined:
        root.findChild(QObject, "outlinedMeasure").setProperty("kind", "outlined")
    pump(QApplication.instance())
    return widget


def _gallery_light(window: object) -> object:
    return _gallery(window)


def _gallery_high_contrast(window: object) -> object:
    return _gallery(window, scheme="high", outlined=True)


SCREENS: list[Screen] = [
    Screen(
        id="sheets.material_controls_gallery",
        area="sheets",
        prepare=_gallery_light,
        checks=(
            "Floating Add button: 56 x 56, corner radius 6, filled with the card colour (#ffffff). "
            "Navigation rail: 80 wide; the selected destination's indicator is 56 x 32. Phone navigation "
            "bar: 80 tall. Segmented button: 40 tall, radius 6, the selected segment shows an 18 x 18 "
            "check. Switch: 52 x 32; off, the thumb is 16 at (8, 8); on (the second switch), it is 24 at "
            "(24, 4). Preset swatch: the disc is 48, the selected check badge is 22 (radius 11). Settings "
            "group: radius 8; row title 16/500 at 16 px top padding, subtitle 14/400; the compact row's "
            "top padding is 10. School event block: fill #e4ebf7, radius 6, 4 px bar, body inset 12 and "
            "6, title 12/600 wrapping to two lines. Past event: fill and bar at 55% opacity, title at "
            "full opacity. Dialog card: 440 wide, radius 8. Snackbar: 48 tall, its top 24 px plus its "
            "height above the bottom of its host. Mini month: today is a 28 px disc. Disabled filled "
            "button: fill is the ink (#0f172a) at 12% and the label at 38%. Disabled text button: no "
            "fill, label at 38%. Enabled filled button: 40 tall, filled with the primary #3d6fc4."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_controls_high_contrast",
        area="sheets",
        prepare=_gallery_high_contrast,
        checks=(
            "In the High contrast scheme an outlined button's stroke is 1.5 px (1 px in the standard "
            "scheme), and every control keeps its size."
        ),
        sources=SOURCES,
        styles=("material",),
    ),
]
