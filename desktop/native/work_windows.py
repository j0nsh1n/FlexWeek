"""The work hours presets and limit shared by first-run setup and Settings."""

from __future__ import annotations

import flexweek_engine  # type: ignore[import-untyped]

MAX_WORK_WINDOWS: int = int(flexweek_engine.MAX_WORK_WINDOWS)
PRESETS: tuple[tuple[str, list[int], str, str], ...] = flexweek_engine.WORK_WINDOW_PRESETS
PRESETS_NOTE: str = str(flexweek_engine.WORK_WINDOW_PRESETS_NOTE)
