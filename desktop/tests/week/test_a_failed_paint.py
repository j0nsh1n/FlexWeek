"""A design's painter that raises must not leave the hours' painter active."""

from __future__ import annotations

import importlib.util
import os

import pytest

from desktop.tests.week.support_painter import qapp, three_days  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtGui import QImage, QPainter  # noqa: E402

from desktop.native.hours import canvas as canvas_module  # noqa: E402


def test_a_paint_that_raises_still_ends_its_painter(monkeypatch: pytest.MonkeyPatch) -> None:
    """A design's painter that raises leaves the hours' painter to the traceback. Still active, it
    outlived the picture a grab painted on, and the collector crashed the worker when it ended the
    painter later, in some other test."""
    seen: list[QPainter] = []

    def raises(painter: QPainter, *_rest: object, **_named: object) -> None:
        seen.append(painter)
        raise RuntimeError("no words")

    monkeypatch.setattr(canvas_module, "_paint_layout", raises)
    canvas = three_days()
    # The test's own picture, so a painter left active can still be ended safely below.
    picture = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    try:
        with pytest.raises(RuntimeError, match="no words"):
            canvas.render(picture)
        assert seen and not seen[0].isActive()
    finally:
        for painter in seen:
            if painter.isActive():
                painter.end()
