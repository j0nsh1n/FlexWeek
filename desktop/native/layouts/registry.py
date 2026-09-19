"""The layouts a student can pick, and what each lets them change.

A layout is a whole way of showing the week, where a look is only paint. There are two roles. A main
view is where planning happens, so it has to offer the whole week, what has no time yet, Add, Plan and
opening a block by itself. A day screen is what you watch once planning is done, so it offers what is
on now, Done, Start focus, Running late and the way back.

Customising comes in three levels, and the dialog is built from this table rather than by hand:
  1. pick   which main view and which day screen
  2. style  each design's colourways, one of which always follows the student's own look
  3. detail what that design shows and how densely

This module is plain data with no Qt in it, so the choices can be checked without a screen.
"""

from __future__ import annotations

from dataclasses import dataclass

from desktop.native.layouts.colourways import BENTO, CLAY, DIAL, MISSION, ONE, RETRO, TIMELINE, Colourways
from desktop.native.look import contrast, mix, readable_ink

MATCH = "match"


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

    @property
    def default(self) -> str:
        return self.choices[0].value

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
    colourways: Colourways = ()


def _colour(spec_colourways: Colourways) -> Option:
    named = tuple(Choice(value, label) for value, label, _ in spec_colourways)
    return Option("colour", "Colours", "style", (*named, Choice(MATCH, "Match my look")))


def _show(key: str, label: str, level: str = "detail") -> Option:
    return Option(key, label, level, (Choice("show", "Show"), Choice("hide", "Hide")))


_HOURS = Option(
    "hours", "Hours shown", "detail", (Choice("day", "06:00 to 22:00"), Choice("full", "All 24 hours"))
)

LAYOUTS: dict[str, LayoutSpec] = {
    spec.id: spec
    for spec in (
        LayoutSpec(
            "classic", "plan", "Today's app", "The week grid with the sidebar. Its colours are the Look menu."
        ),
        LayoutSpec(
            "timeline",
            "plan",
            "Timeline",
            "One day as a column, the week as a strip of load bars.",
            (
                _colour(TIMELINE),
                Option(
                    "density",
                    "Spacing",
                    "style",
                    (Choice("comfortable", "Comfortable"), Choice("compact", "Compact")),
                ),
                # Never "hidden": the strip is how a day is picked, so without it the week is out of reach.
                Option(
                    "strip",
                    "Week strip",
                    "detail",
                    (Choice("bars", "With load bars"), Choice("names", "Day names only")),
                ),
                _show("finished", "Finished and past items"),
            ),
            TIMELINE,
        ),
        LayoutSpec(
            "mission",
            "plan",
            "Mission control",
            "Days as lanes across the screen, with a deadline radar.",
            (_colour(MISSION), _HOURS, _show("side", "Deadline radar and load")),
            MISSION,
        ),
        LayoutSpec(
            "bento",
            "plan",
            "Bento",
            "A home screen of tiles: what is next, deadlines, what has no time yet.",
            (
                _colour(BENTO),
                Option(
                    "corners", "Tile corners", "style", (Choice("soft", "Soft"), Choice("square", "Square"))
                ),
                Option(
                    "tiles",
                    "Tiles",
                    "detail",
                    (Choice("all", "All tiles"), Choice("essentials", "Essentials only")),
                ),
            ),
            BENTO,
        ),
        LayoutSpec(
            "retro",
            "plan",
            "Retro desktop",
            "Windows and a taskbar: the week, a deadlines notepad, what is next.",
            (
                _colour(RETRO),
                Option(
                    "windows",
                    "Windows open at start",
                    "detail",
                    (Choice("all", "All three"), Choice("week", "Only the week")),
                ),
            ),
            RETRO,
        ),
        LayoutSpec(
            "clay",
            "plan",
            "Clay deck",
            "Soft day cards in a deck, one day in the middle.",
            (
                _colour(CLAY),
                Option(
                    "cards", "Cards in the deck", "detail", (Choice("five", "Five"), Choice("three", "Three"))
                ),
                Option("tilt", "Tilted cards", "detail", (Choice("on", "Tilted"), Choice("off", "Straight"))),
            ),
            CLAY,
        ),
        LayoutSpec(
            "one",
            "day",
            "One thing",
            "The whole window is the thing that is on now.",
            (
                _colour(ONE),
                Option(
                    "lead",
                    "Lead with",
                    "detail",
                    (Choice("now", "What is on now"), Choice("next", "What is next")),
                ),
                _show("actions", "Buttons"),
                _show("daybar", "Day bar"),
            ),
            ONE,
        ),
        LayoutSpec(
            "dial",
            "day",
            "Day dial",
            "The day as a clock face, read out hour by hour beside it.",
            (
                _colour(DIAL),
                _HOURS,
                _show("list", "Hour by hour list"),
                _show("week", "Small dials for the week"),
            ),
            DIAL,
        ),
    )
}
MAIN_DEFAULT, DAY_DEFAULT = "classic", "one"
LEVELS = (("style", "Style"), ("detail", "Fine-tune"))


def layouts_for(role: str) -> tuple[LayoutSpec, ...]:
    return tuple(spec for spec in LAYOUTS.values() if spec.role == role)


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
        kept = {
            option.key: values[option.key]
            for option in spec.options
            if values.get(option.key) in option.values
        }
        if kept:
            clean["options"][layout_id] = kept
    return clean


def options_for(choice: dict | None, layout_id: str) -> dict[str, str]:
    """Every option of a layout, as the student set it or as the design ships."""
    stored = sanitize_layout(choice)["options"].get(layout_id, {})
    return {option.key: stored.get(option.key, option.default) for option in LAYOUTS[layout_id].options}


def _tint(accent: str, surface: str, share: float, inks: tuple[str, ...], floor: float = 4.5) -> str:
    """As much of the accent as the text on it can take. A fixed share dipped muted text to 4.49."""
    while share > 0.01:
        colour = mix(accent, surface, share)
        if all(contrast(ink, colour) >= floor for ink in inks):
            return colour
        share *= 0.75
    return surface


def complete(tokens: dict[str, str]) -> dict[str, str]:
    """Fill in what a colourway leaves out from its own colours, never from another palette: white text
    from one over a pale card from another measured 1.15 to 1."""
    inks = (tokens["text"], tokens["muted"])
    cards = {
        f"card_{name}": _tint(tokens["accent"], tokens["surface"], share, inks)
        for name, share in zip("abcd", (0.10, 0.16, 0.22, 0.13), strict=True)
    }
    return {"cta": tokens["accent"], "cta_ink": tokens["accent_ink"], **cards, **tokens}


def match_tokens(palette: dict) -> dict[str, str]:
    """A design in the student's own look: the colours the rest of the app is already wearing."""
    return complete(
        {
            "bg": palette["window"],
            "bg_ink": palette["text"],
            "bg_muted": palette["muted"],
            "surface": palette["panel"],
            "text": palette["text"],
            "muted": palette["muted"],
            "accent": palette["accent"],
            "accent_ink": palette["accent_ink"],
            "line": mix(palette["text"], palette["panel"], 0.22),
            "danger": palette["error"],
            "danger_ink": readable_ink(palette["error"]),
        }
    )


def tokens_for(layout_id: str, colour: str, palette: dict) -> dict[str, str]:
    """The colours a layout paints with. Every design can ask for every token, so a view never has to
    guard a missing key."""
    chosen = next((tokens for value, _, tokens in LAYOUTS[layout_id].colourways if value == colour), None)
    return match_tokens(palette) if chosen is None else complete(chosen)


def contrast_failures(tokens: dict[str, str], floor: float = 4.5) -> list[str]:
    """Every pair of colours a layout puts text on, held to AA. The pairs come from the token names:
    `x_ink` is text on `x`, `text` and `muted` sit on `surface` and on every `card_`, `bg_muted` on `bg`."""
    pairs = [(f"{key}", tokens[key], tokens[key[:-4]]) for key in tokens if key.endswith("_ink")]
    pairs += [(name, tokens[name], tokens["surface"]) for name in ("text", "muted")]
    pairs += [("bg_muted", tokens["bg_muted"], tokens["bg"])]
    pairs += [
        (f"{name} on {key}", tokens[name], tokens[key])
        for key in tokens
        if key.startswith("card_")
        for name in ("text", "muted")
    ]
    return [
        f"{label} {contrast(ink, paper):.2f}" for label, ink, paper in pairs if contrast(ink, paper) < floor
    ]
