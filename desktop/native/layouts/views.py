"""The widget behind each layout id. Kept apart from the registry so that stays free of Qt."""

from __future__ import annotations

from desktop.native.layouts.base import LayoutView
from desktop.native.layouts.bento import BentoView
from desktop.native.layouts.dial import DayDialView
from desktop.native.layouts.one_thing import OneThingView

VIEW_CLASSES: dict[str, type[LayoutView]] = {
    "bento": BentoView,
    "one": OneThingView,
    "dial": DayDialView,
}
