"""The design choice the look file keeps under its `layout` key, and the surface it names.

Plain data with no Qt in it. Today's app is the only design left, but an older look file may name
others, so reading it still sanitizes the choice and writing it back keeps the same keys.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    level: str
    choices: tuple[Choice, ...]
    # The value as the design ships, when that is not the first choice.
    shipped: str = ""

    @property
    def default(self) -> str:
        return self.shipped or self.choices[0].value

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(choice.value for choice in self.choices)


@dataclass(frozen=True)
class LayoutSpec:
    id: str
    role: str
    label: str
    summary: str
    options: tuple[Option, ...] = ()
    purpose: str = ""


DESIGN_LOOKS: dict[str, tuple[tuple[str, str], ...]] = {
    "classic": (
        ("pack:light-frost", "Light"),
        ("preset:high-contrast", "High contrast"),
        ("pack:dark-frost", "Dark"),
        ("preset:paper", "Paper"),
        ("preset:poster", "Poster"),
    ),
}


def _look(layout_id: str) -> Option:
    """Offer the signature first; an unset stored choice continues to wear the student's own look."""
    choices = tuple(Choice(value, label) for value, label in DESIGN_LOOKS[layout_id])
    return Option("look", "Look", "style", (*choices, Choice("your", "Your look")), shipped="your")


LAYOUTS: dict[str, LayoutSpec] = {
    spec.id: spec
    for spec in (
        LayoutSpec(
            "classic",
            "plan",
            "Today's app",
            "The week grid with the sidebar. Its colours come from the look you choose above.",
            (_look("classic"),),
            purpose="Calendar",
        ),
    )
}
MAIN_DEFAULT, DAY_DEFAULT = "classic", "dial"
LEGACY_COLOURS: dict[str, dict[str, str]] = {}


def sanitize_layout(raw: object) -> dict:
    """Whatever the file on disk says, hand back a choice this build can show."""
    clean: dict = {"main": MAIN_DEFAULT, "day": DAY_DEFAULT, "options": {}}
    if not isinstance(raw, dict):
        return clean
    for slot, role in (("main", "plan"), ("day", "day")):
        spec = LAYOUTS.get(raw.get(slot)) if isinstance(raw.get(slot), str) else None
        if spec is not None and spec.role == role:
            clean[slot] = spec.id
    stored = raw.get("options")
    for layout_id, values in (stored if isinstance(stored, dict) else {}).items():
        spec = LAYOUTS.get(layout_id) if isinstance(layout_id, str) else None
        if spec is None or not isinstance(values, dict):
            continue
        old_colour = values.get("colour")
        if "look" not in values and isinstance(old_colour, str):
            values = {**values, "look": LEGACY_COLOURS.get(layout_id, {}).get(old_colour, "your")}
        kept = {
            option.key: values[option.key]
            for option in spec.options
            if values.get(option.key) in option.values
        }
        if kept:
            clean["options"][layout_id] = kept
    return clean


SURFACES = ("material",)
SURFACE_DEFAULT = "material"


def sanitize_surface(raw: object) -> str:
    """The whole-window surface a look file names.

    Material 3 is the only style a student can reach, so whatever the file says, including the
    Widgets value an older build wrote, opens Material. The file is not rewritten for keys this
    does not own.
    """
    return SURFACE_DEFAULT
