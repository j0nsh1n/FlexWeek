"""The Material Week helpers and the `window` fixture other test files take (test_material_open_edit
loads this module as a plugin). They now live in desktop.tests.week.support_material; no test lives
here.
"""

from __future__ import annotations

from desktop.tests.week.support_material import (  # noqa: F401
    _block_named,
    _bridge,
    _centre,
    _click,
    _drag,
    _homework,
    _look,
    _named,
    _pref,
    _pump,
    _qml,
    _reset,
    _snack,
    _week_monday,
)
from desktop.tests.week.support_material import material_window as window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401
