"""The Animations levels and the rules that scale a duration or a distance by one. No Qt, so the shell and
Material read the level the student chose without the painting code in `motion`."""

from __future__ import annotations

from dataclasses import dataclass

import flexweek_engine  # type: ignore[import-untyped]


@dataclass(frozen=True)
class Level:
    """One Animations level. `pace` stretches every duration, 0 being at once; `reach` stretches
    every distance, 0 being fades only."""

    pace: float
    reach: float


# The stored ids (look.MOTION_LEVELS), which saved preferences and custom looks use. "extra" is
# shown as More. Reduce keeps the fades and nothing travels: no slide, rise, drift, zoom or lift.
LEVELS = {name: Level(pace, reach) for name, pace, reach in flexweek_engine.views_theme_motion_levels()}
EASE_MS: int = int(flexweek_engine.MOTION_EASE_MS)

# The level the whole app runs at, for what has no window to ask: dialogs, designs, painted hours.
_app_level = "normal"


def motion_level(preference: object, look_default: object) -> str:
    """The student's Animations setting, or the look's own when they never chose one."""
    return str(flexweek_engine.views_theme_motion_level(preference, look_default))


def set_app_level(level: str) -> None:
    """Make `level` the app's, or Normal when it is not a level."""
    global _app_level
    _app_level = str(flexweek_engine.views_theme_motion_level(level, None))


def app_level() -> str:
    return _app_level


def duration(ms: int, level: str | None = None) -> int:
    """How long Normal's `ms` takes at `level`, or at the app's; 0 is at once."""
    return int(flexweek_engine.views_theme_motion_duration(ms, level, _app_level))


def distance(px: int, level: str | None = None) -> int:
    """How far Normal's `px` goes at `level`, or at the app's; 0 under Reduce and Off."""
    return int(flexweek_engine.views_theme_motion_distance(px, level, _app_level))


def moves(level: str | None = None) -> bool:
    """Whether things travel at `level`, or at the app's, rather than only fading or not moving."""
    return bool(flexweek_engine.views_theme_motion_moves(level, _app_level))
