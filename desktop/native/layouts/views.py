"""The widget behind each layout id. Kept apart from the registry so that stays free of Qt."""

from __future__ import annotations

from desktop.native.layouts.base import LayoutView
from desktop.native.layouts.bento import BentoView
from desktop.native.layouts.retro import RetroView
from desktop.native.layouts.timeline import TimelineView

VIEW_CLASSES: dict[str, type[LayoutView]] = {
    "timeline": TimelineView,
    "bento": BentoView,
    "retro": RetroView,
}
