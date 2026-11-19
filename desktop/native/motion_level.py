"""The Animations levels and the rules that scale a duration or a distance by one. No Qt, so the shell and
Material read the level the student chose without the painting code in `motion`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    """One Animations level. `pace` stretches every duration, 0 being at once; `reach` stretches
    every distance, 0 being fades only."""

    pace: float
    reach: float


# The stored ids (look.MOTION_LEVELS), which saved preferences and custom looks use. "extra" is
# shown as More. Reduce keeps the fades and nothing travels: no slide, rise, drift, zoom or lift.
# More is 2.5 times as slow, so the standard planning ease of 220 ms is 550 ms. At 1.45 it was
# hard to tell from Normal.
LEVELS = {
    "normal": Level(1.0, 1.0),
    "extra": Level(2.5, 4 / 3),
    "reduce": Level(1.0, 0.0),
    "off": Level(0.0, 0.0),
}
# Notices, dialogs, blocks settling after a plan: long enough to see where things went, short
# enough never to feel like waiting.
EASE_MS = 220

# The level the whole app runs at, for what has no window to ask: dialogs, designs, painted hours.
_app_level = "normal"


def motion_level(preference: object, look_default: object) -> str:
    """The student's Animations setting, or the look's own when they never chose one."""
    if preference in LEVELS:
        return str(preference)
    return str(look_default) if look_default in LEVELS else "normal"


def set_app_level(level: str) -> None:
    """Make `level` the app's, or Normal when it is not a level."""
    global _app_level
    _app_level = level if level in LEVELS else "normal"


def app_level() -> str:
    return _app_level


def duration(ms: int, level: str | None = None) -> int:
    """How long Normal's `ms` takes at `level`, or at the app's; 0 is at once."""
    return round(ms * LEVELS[level or _app_level].pace)


def distance(px: int, level: str | None = None) -> int:
    """How far Normal's `px` goes at `level`, or at the app's; 0 under Reduce and Off."""
    return round(px * LEVELS[level or _app_level].reach)


def moves(level: str | None = None) -> bool:
    """Whether things travel at `level`, or at the app's, rather than only fading or not moving."""
    return LEVELS[level or _app_level].reach > 0


def frame_interval_ms(rate: float) -> int:
    """How many milliseconds between frames at `rate` Hz. An unknown rate, or one too low to be a
    screen, is 60. The interval is never 0, which would run the next frame inside the same turn."""
    if rate <= 1:
        return round(1000 / 60)
    return max(1, round(1000 / rate))
