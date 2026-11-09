"""The "No time yet" rows in the rail: one row per open session, each with its own length."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.weekmodel import Waiting
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_not_placed_rows_keep_each_open_sessions_length(qapp, window: NativeWindow) -> None:
    rail = window.rail
    rail.set_waiting(
        (
            Waiting("hist-1", "History essay", "assignments", 60, "history", None, ""),
            Waiting("hist-2", "History essay", "assignments", 30, "history", None, ""),
        ),
        {"history": 90},
    )

    assert [chip.length for chip in rail.chips()] == ["1 h", "30 min"]
