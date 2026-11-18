"""The work hours presets and limit shared by first-run setup and Settings."""

from __future__ import annotations

MAX_WORK_WINDOWS = 21
PRESETS = (
    ("After school", [0, 1, 2, 3, 4], "15:30", "18:00"),
    ("Evenings", [0, 1, 2, 3, 4], "19:00", "21:00"),
    ("Weekend mornings", [5, 6], "10:00", "12:00"),
)
PRESETS_NOTE = "Each adds a row of hours you can change."
