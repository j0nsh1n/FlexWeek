"""The selected block's outline goes when the block goes or when planning moves things."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_block_that_is_gone_takes_its_outline_with_it(window: NativeWindow) -> None:
    session = window.session
    session.add_block(
        {
            "id": "gym",
            "title": "Gym",
            "kind": "locked",
            "category": "extra",
            "start": "16:00",
            "duration_min": 60,
            "days": [0],
        }
    )
    session.select_block("gym", None)
    session.blocks = [item for item in session.blocks if item["id"] != "gym"]
    session._touch("running late")
    assert session.selected_block_id is None


def test_plan_takes_the_outline_off_the_block_it_was_on(window: NativeWindow) -> None:
    session = window.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:30",
            "duration_min": 405,
            "days": [0, 1, 2, 3, 4],
        }
    )
    session.select_block("school", None)
    session.solve()
    assert session.selected_block_id is None
