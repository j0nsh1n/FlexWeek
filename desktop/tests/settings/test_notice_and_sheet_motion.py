"""Notices rise into place: each ends where it belongs and leaves no effect behind."""

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
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import (
        QApplication,
        QLabel,
        QWidget,
    )

    from desktop.native.motion import (
        EASE_MS,
        appear,
        apply_ui_effects,
        duration,
    )
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


def a_notice(qapp: QApplication) -> tuple[QWidget, QLabel]:  # noqa: F811
    host = QWidget()
    host.resize(400, 300)
    notice = QLabel("Saved.", host)
    notice.move(40, 60)
    host.show()
    qapp.processEvents()
    return host, notice


def test_a_notice_rises_into_place_and_leaves_no_effect_behind(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    host, notice = a_notice(qapp)
    appear(notice, "normal", rise=True)
    effect = notice.graphicsEffect()
    assert effect is not None and effect.offset == QPoint(0, 8), "it starts 8 pixels low"
    assert (notice.x(), notice.y()) == (40, 60), "painted low: the notice itself is already in place"
    manual_time.advance(duration(EASE_MS, "normal") // 2)
    # Half of the 220 ms planning ease on the out-cubic curve: 1 - (1 - 1/2)^3 = 7/8 of the way,
    # so 1/8 of the 8 pixels is left.
    assert effect.opacity == pytest.approx(0.875) and effect.offset == QPoint(0, 1)
    manual_time.advance(duration(EASE_MS, "normal") // 2)
    assert (notice.x(), notice.y()) == (40, 60)
    assert notice.graphicsEffect() is None, "an effect left in place slows every later repaint"
    host.close()


def test_an_animation_cut_short_by_another_leaves_the_widget_where_it_belongs(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """Stopping an animation does not say it finished, so its tidying has to happen anyway. A notice
    shown twice in a row rose from wherever the first rise had got to, and stayed that far down."""
    host, notice = a_notice(qapp)
    appear(notice, "extra", rise=True)
    manual_time.advance(40)
    appear(notice, "extra", rise=True)
    manual_time.advance(duration(EASE_MS, "extra"))
    assert (notice.x(), notice.y()) == (40, 60)
    assert notice.graphicsEffect() is None
    host.close()
