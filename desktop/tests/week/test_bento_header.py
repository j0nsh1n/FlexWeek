"""Bento's week header: every day writes its whole day word and its date, at any width and text size.

Regression from 1024 px wide with large text, where empty weekend columns painted a day word short or
not at all. (Where the headers sit over their columns is the picture week.bento_week.)"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.calendar import DAYS  # noqa: E402
from desktop.native.layouts import bento  # noqa: E402
from desktop.native.layouts.registry import MATCH, tokens_for  # noqa: E402
from desktop.native.look import resolved_palette  # noqa: E402
from desktop.tests.light_app import window  # noqa: E402, F401
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-bento-header-test"])


def watch_headers(monkeypatch: pytest.MonkeyPatch, painted: dict[str, list[str]]) -> None:
    """Keep the words every Bento day header writes, by the header's object name."""

    class Observed(QPainter):
        def __init__(self, device) -> None:
            super().__init__(device)
            named = isinstance(device, QPushButton) and device.objectName().startswith("bentoDayName")
            self.header = device.objectName() if named else ""

        def drawText(self, *args) -> None:  # noqa: N802
            if self.header and args:
                for arg in reversed(args):
                    if isinstance(arg, str):
                        painted.setdefault(self.header, []).append(arg)
                        break
            return super().drawText(*args)

    monkeypatch.setattr(bento, "QPainter", Observed)


@pytest.mark.parametrize(("width", "text"), [(1024, "normal"), (1280, "large"), (1024, "large")])
def test_every_day_header_writes_its_day_word_and_date(
    qapp: QApplication, window, monkeypatch: pytest.MonkeyPatch, width: int, text: str
) -> None:
    painted: dict[str, list[str]] = {}
    watch_headers(monkeypatch, painted)
    session = window.session
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._look = {"preset": "ink", "knobs": {"text": text}}
    session.look = window._look
    window._apply_appearance()
    window._on_week()
    window.resize(width, 860)
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    qapp.processEvents()
    assert window.width() == width
    week_start = date.fromisoformat(session.week_start)
    for day in range(7):
        name = f"bentoDayName{day}"
        header = window.findChild(QPushButton, name)
        assert header is not None and header.isVisible(), name
        painted[name] = []
        assert not header.grab().isNull(), name
        expected = [DAYS[day], str((week_start + timedelta(days=day)).day)]
        assert painted[name] == expected, (name, width, text)


def test_a_narrow_header_does_not_shorten_to_a_single_letter_and_digit(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    painted: dict[str, list[str]] = {}
    watch_headers(monkeypatch, painted)
    tokens = tokens_for("bento", MATCH, resolved_palette("light-frost", False, None))
    head = bento.DayHead(4)
    head.show_date(2, True, head.ink, tokens, 1.25)
    head.resize(52, 36)
    head.grab()
    assert painted[head.objectName()] == [DAYS[4], "2"]
