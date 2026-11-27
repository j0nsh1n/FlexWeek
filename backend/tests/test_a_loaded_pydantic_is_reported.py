"""The window check names pydantic when it is loaded, without starting the window.

desktop/tests/conftest.py imports the window, and that import needs a current engine build. This
file does not, so a planted module can make the check fail on its own.
"""

from __future__ import annotations

import sys
import types

import pytest

from backend.tests.pydantic_loaded import pydantic_loaded

PLANTED = (
    "pydantic",
    "pydantic.main",
    "pydantic_core",
    "pydantic_core._pydantic_core",
)
DECOY = "pydantic_core_not_the_package"


def test_a_planted_pydantic_or_pydantic_core_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A module put in sys.modules is reported, a lookalike is not, and removing them clears the report."""
    for name in PLANTED:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, DECOY, types.ModuleType(DECOY))
    found = pydantic_loaded()
    missed = [name for name in PLANTED if name not in found]
    extra = [DECOY] if DECOY in found else []
    assert missed == [] and extra == [], f"missed {missed}, extra {extra}"
    for name in PLANTED:
        del sys.modules[name]
    still = [name for name in PLANTED if name in pydantic_loaded()]
    assert still == []
