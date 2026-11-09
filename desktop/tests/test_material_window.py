# ruff: noqa: F811
"""Names other test files import from here. No tests: the Material shell's tests are in
desktop/tests/day/test_material_shell_*.py, desktop/tests/week/test_material_week_contents.py,
desktop/tests/sheets/ and desktop/tests/focus/test_material_focus_in_shell.py. The helpers are in
desktop/tests/material_support.py and the signed-in window in desktop/tests/day/support_material_window.py."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.day.support_material_window import (  # noqa: E402, F401
    FALLBACK,
    HOUR_ROW,
    NIGHT,
    SCHOOL_LIGHT,
    qapp,
    window,
)
from desktop.tests.material_support import named as _named  # noqa: E402, F401
from desktop.tests.material_support import pump as _pump  # noqa: E402, F401
from desktop.tests.material_support import qml as _qml  # noqa: E402, F401
from desktop.tests.material_support import repeater_texts as _repeater_texts  # noqa: E402, F401
from desktop.tests.material_support import show_material as _show_material  # noqa: E402, F401
from desktop.tests.material_support import visuals as _visuals  # noqa: E402, F401
