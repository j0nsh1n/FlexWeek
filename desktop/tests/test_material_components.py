"""Names other test files import from here (and use as a pytest plugin for the `gallery` and `qapp`
fixtures). No tests: the controls' keyboard tests are in
desktop/tests/sheets/test_material_gallery_controls.py and the gallery's helpers in
desktop/tests/sheets/support_material_gallery.py."""

from __future__ import annotations

from desktop.tests.sheets.support_material_gallery import (  # noqa: F401
    QML,
    ROOT,
    _child,
    _color,
    _find,
    _press,
    _walk,
    gallery,
    qapp,
)
