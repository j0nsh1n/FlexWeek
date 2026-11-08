# ruff: noqa: F401
"""No tests here: the Material sheet tests live in desktop/tests/sheets/. This module stays only so the
files that still import its names (test_material_discard_prompt.py, as a pytest plugin and for `_find` and
`_type_homework`) keep working until they move too."""

from desktop.tests.sheets.support_material_sheets import (
    find_named as _find,
)
from desktop.tests.sheets.support_material_sheets import (
    open_light,
    qapp,
    sheets,
    shell,
)
from desktop.tests.sheets.support_material_sheets import (
    type_homework as _type_homework,
)
