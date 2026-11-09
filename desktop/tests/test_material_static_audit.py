"""Names other test files import from here. No tests: the Settings preview tests are in
desktop/tests/sheets/test_material_settings_preview.py and their helpers in
desktop/tests/sheets/support_material_settings.py."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.material_support import named as _named  # noqa: E402, F401
from desktop.tests.sheets.support_material_settings import bridge as _bridge  # noqa: E402, F401
from desktop.tests.sheets.support_material_settings import panel as _panel  # noqa: E402, F401
