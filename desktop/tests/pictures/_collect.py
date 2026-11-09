"""Gathers the screens the views lane wrote in its fragment modules (`_<area>_g<NN>.py`, one per
helper and area) so each `screens_<area>.py` can declare one list. A fragment may hold screens of
another area than its name says; this picks them by the Screen's own area."""

from __future__ import annotations

import importlib
import pkgutil

from desktop.tests.pictures.screen import Screen


def screens_of(area: str) -> list[Screen]:
    from desktop.tests import pictures

    found: list[Screen] = []
    for module in sorted(info.name for info in pkgutil.iter_modules(pictures.__path__)):
        if module.startswith("_") and "_g" in module:
            found.extend(
                screen
                for screen in importlib.import_module(f"{pictures.__name__}.{module}").SCREENS
                if screen.area == area
            )
    return found
