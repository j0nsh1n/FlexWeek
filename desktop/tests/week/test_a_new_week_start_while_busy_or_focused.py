"""Picking a new first day of the week while the window is busy, or while a focus timer runs. The clock
is Thursday 5 November 2026: from Monday the open week runs Monday 2 to Sunday 8 November, from
Wednesday it runs Wednesday 4 to Tuesday 10, where Thursday 5 is day 1."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native import fields
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_week_start_picked_while_a_week_loads_opens_its_week_when_the_load_lands(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    assert session.week_start == "2026-11-02"
    session.load_week(session.week_start, discard=True)
    assert session.busy
    fields.save_week_starts_on("wednesday")
    wait_until(
        qapp,
        lambda: session.week_start == "2026-11-04" and not session.busy,
        timeout=5,
        what=lambda: f"open week {session.week_start}, busy {session.busy}",
    )

