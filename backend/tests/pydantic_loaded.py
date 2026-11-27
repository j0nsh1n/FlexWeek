"""The names pydantic and pydantic_core among this process's loaded modules.

The window test and the planted-module test share this, so a stale engine wheel is not what makes
the check go red.
"""

from __future__ import annotations

import sys


def pydantic_loaded() -> list[str]:
    return sorted(
        name
        for name in sys.modules
        if name in {"pydantic", "pydantic_core"} or name.startswith(("pydantic.", "pydantic_core."))
    )
