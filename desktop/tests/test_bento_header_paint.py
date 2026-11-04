"""Regression test: Bento day headers paint complete day word AND date without clipping.

At 1024px narrow width with large text, empty weekend buttons (Saturday/Sunday) must paint both
the day name (e.g., 'Sat', 'Sun') and the date number, matching normal text control and wide (1280px)
allocations, while maintaining canvas track alignment.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QPushButton

from desktop.native.calendar import DAYS
from desktop.native.layouts import bento
from desktop.native.layouts.bento import BentoCanvas
from desktop.tests.test_regress_item4_button_labels import dress
from desktop.tests.window_support import qapp, server, settled, signed_out, window  # noqa: F401


def test_bento_headers_paint_day_word_and_date_and_align_to_canvas(
    qapp, window, monkeypatch
) -> None:
    """Verify all seven Bento day headers paint non-empty day names and dates at narrow (1024)
    and wide (1280) widths across large and normal text, without omitting the day word on
    empty weekend columns, and remain aligned to canvas tracks.
    """
    painted: dict[str, list[str]] = {}

    class SafePaintObserver(QPainter):
        def __init__(self, device):
            super().__init__(device)
            if isinstance(device, QPushButton):
                name = device.objectName()
                self.target_name = name if name.startswith("bentoDayName") else ""
            else:
                self.target_name = ""

        def drawText(self, *args):  # noqa: N802
            if self.target_name and args:
                for arg in reversed(args):
                    if isinstance(arg, str):
                        painted.setdefault(self.target_name, []).append(arg)
                        break
            return super().drawText(*args)

    monkeypatch.setattr(bento, "QPainter", SafePaintObserver)

    week_start = date.fromisoformat(window.session.week_start)

    # First run normal control and wide cases, then narrow/large empty weekend
    cases = [
        (1024, "normal"),
        (1280, "large"),
        (1024, "large"),
    ]

    for width, size in cases:
        dress(qapp, window, "bento", "ink", size)
        window._on_week()
        window.resize(width, 860)
        settled(qapp, window)
        qapp.processEvents()

        assert window.width() == width, f"Requested width {width} was reset to {window.width()}"

        canvas = next(
            c for c in window.findChildren(BentoCanvas) if len(c.tracks) == 7 and c.isVisible()
        )

        for day_idx in range(7):
            ident = f"bentoDayName{day_idx}"
            button = window.findChild(QPushButton, ident)
            assert button is not None, f"Button {ident} not found"
            assert button.isVisible(), f"Button {ident} not visible at {width}px {size}"

            expected_day = DAYS[day_idx]
            expected_date = str((week_start + timedelta(days=day_idx)).day)

            painted[ident] = []
            pixmap = button.grab()
            assert not pixmap.isNull(), f"Failed to grab pixmap for {ident}"

            records = painted.get(ident, [])
            assert records, f"No paint operations observed for {ident} at {width}px {size}"
            assert all(records), (
                f"{ident} ({width}px, {size}) painted empty text component: {records}"
            )
            assert records == [expected_day, expected_date], (
                f"{ident} ({width}px, {size}) painted {records}, expected {[expected_day, expected_date]}"
            )

            # Seven headers align to canvas tracks
            track = next(t for t in canvas.tracks if t.day == day_idx)
            start = button.mapToGlobal(button.rect().topLeft()).x()
            track_start = canvas.mapToGlobal(canvas.rect().topLeft()).x() + track.area.left() - 2
            assert abs(start - track_start) <= 6.0, (
                f"Header {ident} misaligned with canvas track: button_x={start}, track_x={track_start}"
            )
