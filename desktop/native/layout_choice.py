"""The design choice the look file keeps under its `layout` key, and the surface it names.

Plain data with no Qt in it. Today's app is the only design left, but an older look file may name
others, so reading it still sanitizes the choice and writing it back keeps the same keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]


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
        return str(flexweek_engine.views_look_option_default(self.shipped, self.choices[0].value))

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


def _build_design_looks() -> dict[str, tuple[tuple[str, str], ...]]:
    raw: dict[str, list[list[str]]] = json.loads(flexweek_engine.views_look_design_looks())
    return {
        layout_id: tuple((str(value), str(label)) for value, label in pairs)
        for layout_id, pairs in raw.items()
    }


def _build_option(item: dict[str, Any]) -> Option:
    return Option(
        str(item["key"]),
        str(item["label"]),
        str(item["level"]),
        tuple(Choice(str(choice["value"]), str(choice["label"])) for choice in item["choices"]),
        shipped=str(item["shipped"]),
    )


def _build_layouts() -> dict[str, LayoutSpec]:
    raw: list[dict[str, Any]] = json.loads(flexweek_engine.views_look_layouts())
    return {
        str(spec["id"]): LayoutSpec(
            str(spec["id"]),
            str(spec["role"]),
            str(spec["label"]),
            str(spec["summary"]),
            tuple(_build_option(option) for option in spec["options"]),
            purpose=str(spec["purpose"]),
        )
        for spec in raw
    }


DESIGN_LOOKS: dict[str, tuple[tuple[str, str], ...]] = _build_design_looks()
LAYOUTS: dict[str, LayoutSpec] = _build_layouts()
MAIN_DEFAULT: str = str(flexweek_engine.LOOK_MAIN_DEFAULT)
DAY_DEFAULT: str = str(flexweek_engine.LOOK_DAY_DEFAULT)
LEGACY_COLOURS: dict[str, dict[str, str]] = {}


def sanitize_layout(raw: object) -> dict:
    """Whatever the file on disk says, hand back a choice this build can show."""
    return json.loads(flexweek_engine.views_look_sanitize_layout(raw))


SURFACES: tuple[str, ...] = tuple(flexweek_engine.LOOK_SURFACES)
SURFACE_DEFAULT: str = str(flexweek_engine.LOOK_SURFACE_DEFAULT)


def sanitize_surface(raw: object) -> str:
    """The whole-window surface a look file names.

    Material 3 is the only style a student can reach, so whatever the file says, including the
    Widgets value an older build wrote, opens Material. The file is not rewritten for keys this
    does not own.
    """
    return str(flexweek_engine.views_look_sanitize_surface(raw))
