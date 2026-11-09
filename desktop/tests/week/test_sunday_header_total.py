"""Sunday's homework total reads "45 min" in its column header, in the week and beside the rail."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.hours.classic import GUTTER, Colours, DayName, column_widths  # noqa: E402
from desktop.native.layouts.registry import sanitize_layout  # noqa: E402
from desktop.native.look import resolved_palette, sanitize_look  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401


def test_sundays_header_total_is_said_whole_at_810_px_large(qapp: object) -> None:
    look = {"preset": "default", "knobs": {"text": "large"}}
    palette = resolved_palette("system", False, look)
    widths = column_widths(810 - GUTTER, frozenset({6}), days=tuple(range(7)))
    name = DayName(6)
    name.colours = Colours.of(palette)
    name.look = look
    name.show_day("Sun", "12", 45, False)
    name.resize(int(widths[6]), name.sizeHint().height())
    assert name.homework_words() == "45 min"


def test_sundays_header_total_is_said_whole_at_810_large_with_the_rail(
    qapp: object, open_light: Callable[..., NativeWindow]
) -> None:
    """810 px, Large text, Agenda rail shown, Sunday's '45 min' in its header."""
    window = open_light()
    session = window.session
    due = sunday_due(session.week_start)
    session.add_homework(
        {"id": "sun45", "title": "Sunday reading", "due": due, "estimate_min": 45, "revision": 0}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = next(block for block in session.blocks if block.get("assignment_id") == "sun45")
    session.add_block({**block, "start": "16:00", "days": [6], "pinned": True})
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._layout = sanitize_layout({"main": "classic", "day": "one"})
    window._apply_appearance()
    session.set_view("week")
    window.resize(810, 860)
    window._on_week()
    wait_until(qapp, lambda: window.week_table._name_labels[6].homework == 45)
    sunday = window.week_table._name_labels[6]
    assert window.rail.isVisible() and not window.rail.folded
    assert sunday.homework == 45
    assert sunday.homework_words() == "45 min"
