"""The contract between the one hand and whatever a design draws its hours on.

A test design here shows the week on every kind of surface at once: columns that run down, lanes
that run across, a card laid at an angle, a day cut into two tiles, and a dial. The same hand has to
land a block on each, keep it inside each tile's own hours, open a day from its name either way time
runs, and hold the design's renders from the moment of the press.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


from desktop.tests.week.support_hand import Stage, stage_of  # noqa: E402, F401
from desktop.tests.window_support import qapp  # noqa: E402, F401

HOURS = Path(__file__).resolve().parents[2] / "native" / "hours"
















def test_nothing_in_the_app_uses_system_drag_and_drop() -> None:
    """Every block moves through the one hand. Qt's system drag and drop is where Wayland and X11
    differ and where the rig cannot see what the student sees, so nothing may take it up again."""
    app = HOURS.parent
    system_drag = r"\bQDrag\b|\bQMimeData\b|\bsetAcceptDrops\b|\bdropEvent\b"
    found = [
        f"{path.relative_to(app)}: {match.group()}"
        for path in sorted(app.rglob("*.py"))
        for match in re.finditer(system_drag, path.read_text())
    ]
    assert found == []
