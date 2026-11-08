"""The name of a block taller than the screen is kept in sight at the top of what shows. A repaint of
a strip in its middle, as when a message over it goes away, must not write it there too."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect, QRectF  # noqa: E402
from PySide6.QtGui import QImage, QPainter, QRegion  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.hours import canvas as canvas_module  # noqa: E402
from desktop.tests.week import support_zoom  # noqa: E402
from desktop.tests.week.support_zoom import SCHOOL, a_day  # noqa: E402

qapp = support_zoom.qapp  # a fixture is found by its name in the test module


def test_a_small_repaint_does_not_write_a_long_blocks_name_again(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Instead of looking at the picture for ink, this records where the painter is asked to write the
    name: it is the paint code's decision that must not follow the repainted strip."""
    wrote: list[tuple[str, QRectF]] = []

    class Heard(QPainter):
        def drawText(self, *args) -> None:  # noqa: N802
            box = args[0]
            if isinstance(box, QRect | QRectF):
                words = next((arg for arg in reversed(args) if isinstance(arg, str)), "")
                wrote.append((words, self.transform().mapRect(QRectF(box))))
            super().drawText(*args)

    monkeypatch.setattr(canvas_module, "QPainter", Heard)
    view = a_day(qapp, [SCHOOL], 0)
    hours = view.hours
    track = hours.track_for(0)
    assert track is not None
    top, bottom = round(track.point_for(8 * 60).y()), round(track.point_for(14 * 60 + 30).y())
    view.scroll.verticalScrollBar().setValue(top - 20)
    image = QImage(hours.size(), QImage.Format.Format_ARGB32)
    image.fill(0)

    # The same spy must see the name when the whole hours are drawn, or it proves nothing below.
    hours.render(image)
    assert any("School" in words for words, _ in wrote), "the name was not written when all was drawn"

    wrote.clear()
    strip = QRect(0, (top + bottom) // 2, hours.width(), 40)
    hours.render(image, strip.topLeft(), QRegion(strip))
    inside = [words for words, box in wrote if "School" in words and box.intersects(QRectF(strip))]
    assert inside == [], "a repaint of a strip in the middle wrote the name there"
