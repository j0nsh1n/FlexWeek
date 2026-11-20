"""Reading the device's look file: the preset and knobs the engine checks, and the motion level a look
starts at. No Qt.

Material 3 draws everything and keeps its own choices in the look file; what is left here is what the
window and the session read from the stored look (`sanitize_look`, `effective_look`, `look_motion`,
`pack_axis`). The checking itself is the engine's.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Callable

import flexweek_engine  # type: ignore[import-untyped]

from desktop.native.wire import plain, restore, restored

# Customise (plan, 27 September): one of the ten looks as a starting point and what the student changed
# on it. Each base is the (pack, preset) it stands for; a custom look ignores the account's pack.
LOOK_BASES = {
    "light": ("light-frost", "default"),
    "dark": ("dark-frost", "default"),
    "system": ("system", "default"),
    "high-contrast": ("system", "high-contrast"),
    "slate": ("slate", "default"),
    "nocturne": ("nocturne", "default"),
    "paper": ("system", "paper"),
    "ink": ("system", "ink"),
    "terminal": ("system", "terminal"),
    "poster": ("system", "poster"),
    "pastel": ("system", "pastel"),
}
# The motion levels of decision 33; Lane F's motion.py runs them.
MOTION_LEVELS = ("normal", "extra", "reduce", "off")

_LOOK_JSON_CACHE: OrderedDict[str, str] = OrderedDict()
_LOOK_JSON_CACHE_MAX = 128


def _look_json_key(raw: object) -> str:
    return plain(raw)


def _cached_look_json(kind: str, key: str, fetch: Callable[[], str]) -> str:
    slot = f"{kind}\0{key}"
    hit = _LOOK_JSON_CACHE.get(slot)
    if hit is not None:
        _LOOK_JSON_CACHE.move_to_end(slot)
        return hit
    hit = fetch()
    _LOOK_JSON_CACHE[slot] = hit
    if len(_LOOK_JSON_CACHE) > _LOOK_JSON_CACHE_MAX:
        _LOOK_JSON_CACHE.popitem(last=False)
    return hit


def known_pack(pack: object) -> str:
    return str(flexweek_engine.look_known_pack(pack))


def pack_axis(pack: object) -> str:
    chosen = known_pack(pack)
    if chosen in {"light-frost", "slate"}:
        return "slate"
    if chosen in {"dark-frost", "nocturne"}:
        return "nocturne"
    return "system"


def sanitize_custom(raw: object) -> tuple[dict | None, list[str]]:
    """A custom look with every unknown key and bad value dropped, and a plain sentence for each one
    dropped. None when there is no look to keep: no base, or one this FlexWeek does not have."""
    key = _look_json_key(raw)
    text = _cached_look_json("sanitize_custom", key, lambda: flexweek_engine.look_sanitize_custom(key))
    custom, problems = restore(json.loads(text))
    return custom, problems


def sanitize_look(raw: object) -> dict:
    """The device's look: a preset and the knobs moved on it, 0.16's knob names read as today's, and a
    custom look when the student made one."""
    key = _look_json_key(raw)
    text = _cached_look_json("sanitize_look", key, lambda: flexweek_engine.look_sanitize_look(key))
    return restored(text)


def effective_look(choice: dict | None) -> dict:
    """Every knob as it is drawn. A custom look's measures answer as the nearest knob, so what reads a
    knob, such as the text size carried to the sign-in screens, still reads something true."""
    key = _look_json_key(choice)
    text = _cached_look_json("effective_look", key, lambda: flexweek_engine.look_effective_look(key))
    return restored(text)


def look_motion(look: dict | None) -> str:
    """The motion level a look starts at when the student never chose one: a custom look's own, Reduce
    for Paper ("distinct page turns, sharp transitions"), else Normal. Light and Dark once started at
    More, 0.16's leftover, so choosing Light moved more than System did."""
    selected = sanitize_look(look)
    custom = selected.get("custom")
    if custom is not None:
        return custom.get("motion") or ("reduce" if LOOK_BASES[custom["base"]][1] == "paper" else "normal")
    return "reduce" if selected["preset"] == "paper" else "normal"
