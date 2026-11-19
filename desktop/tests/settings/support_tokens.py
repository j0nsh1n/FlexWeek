"""The ten looks as a student reaches them, shared by the token tests and the settings pictures.

Colours are measured in OKLab, the space the category family is chosen in; a distance is OKLab's
times 100. Colour blindness is Machado, Oliveira and Fernandes (2009) at full severity, applied to
linear sRGB.
"""

from __future__ import annotations

from itertools import product

from desktop.native.look import ACCENTS, LOOK_KNOBS, resolved_palette


def preset(name: str) -> dict:
    return {"preset": name, "knobs": {}}


# Each look as a student reaches it, on the device setting that goes with it. A preset is the same
# look on any pack, so each is reached from the device's opposite setting too.
LOOKS = {
    "Light": ("light-frost", False, None),
    "Dark": ("dark-frost", True, None),
    "High contrast": ("system", False, preset("high-contrast")),
    "Slate": ("slate", False, None),
    "Nocturne": ("nocturne", True, None),
    "Paper": ("system", True, preset("paper")),
    "Ink": ("system", False, preset("ink")),
    "Terminal": ("slate", False, preset("terminal")),
    "Poster": ("nocturne", True, preset("poster")),
    "Pastel": ("system", True, preset("pastel")),
}
CASES = [(name, surface, accent) for name, surface, accent in product(LOOKS, LOOK_KNOBS["surface"], ACCENTS)]


def look_for(name: str, surface: str = "layered") -> dict:
    look = LOOKS[name][2] or {"preset": "default", "knobs": {}}
    return {**look, "knobs": {**look["knobs"], "surface": surface}}


def palette_for(name: str, surface: str = "layered", accent: str = "default") -> dict:
    pack, dark, _look = LOOKS[name]
    return resolved_palette(pack, dark, look_for(name, surface), accent)






