"""A block's words are laid in whole lines: none is cut in half by the edge of the room it has."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtGui import QFont, QFontMetricsF
    from PySide6.QtWidgets import QApplication

    from desktop.native.hours.canvas import fit_lines

DETAIL = "16:00–17:30 · 1 h 30 min · Missed · Pinned"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-painter-test"])


def fits(lines: list[str], font: QFont, width: float) -> bool:
    metrics = QFontMetricsF(font)
    return all(metrics.horizontalAdvance(line) <= width for line in lines)


def test_room_for_one_line_gives_one_shortened_line(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(DETAIL) / 2
    lines = fit_lines(DETAIL, font, width, metrics.height())
    assert len(lines) == 1
    assert lines[0].endswith("…")
    assert fits(lines, font, width)


def test_room_for_two_and_a_half_lines_gives_two(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–17:30 · 1 h") + 1
    lines = fit_lines(DETAIL, font, width, 2.5 * metrics.lineSpacing())
    assert lines[0] == "16:00–17:30 · 1 h"
    assert len(lines) == 2
    assert lines[1].endswith("…")
    assert fits(lines, font, width)


def test_ample_room_says_it_all(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–17:30 · 1 h") + 1
    lines = fit_lines(DETAIL, font, width, 20 * metrics.lineSpacing())
    assert " ".join(lines) == DETAIL
    assert len(lines) >= 3
    assert fits(lines, font, width)


def test_a_word_wider_than_the_room_is_shortened_and_the_rest_still_follows(qapp: QApplication) -> None:
    font = QFont()
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance("16:00–1")
    lines = fit_lines("16:00–17:30 · 1 h", font, width, 20 * metrics.lineSpacing())
    assert lines[0].endswith("…") and lines[0] != "16:00–17:30"
    assert lines[1:] == ["· 1 h"]
    assert fits(lines, font, width)


def test_no_room_for_a_whole_line_gives_nothing(qapp: QApplication) -> None:
    font = QFont()
    assert fit_lines(DETAIL, font, 400, QFontMetricsF(font).height() - 1) == []
