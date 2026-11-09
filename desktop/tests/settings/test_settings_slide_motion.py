"""Settings slides in over the week, dimmed, and the page that slides is drawn once, not on every frame."""

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
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget

    from desktop.native.motion import OVER_MS, Dim, apply_ui_effects, duration, slide_over
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.settings.support_motion import move_on, pictures, slides, two_pages
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


def test_settings_slides_in_from_the_right_over_the_page_dimmed(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """Settings slides in over the week dimmed 20 %, rather than fading over it."""
    stack, first, second = two_pages(qapp)
    slide_over(stack, second, "normal")
    assert stack.currentWidget() is second and second.graphicsEffect() is None
    (coming,) = slides(stack)
    assert coming.pos() == QPoint(stack.width(), 0), "its picture starts off the right edge"
    (week,) = pictures(stack)
    kids = stack.children()
    assert kids.index(week) < kids.index(coming), "the page it covers stays under it"
    assert len(week.findChildren(Dim)) == 1
    manual_time.advance(duration(OVER_MS, "normal") // 2)
    assert 0 < coming.x() < stack.width()
    assert 0 < week.findChildren(Dim)[0].share < 1, "the page under it is dimming"
    move_on(manual_time, duration(OVER_MS, "extra") + 150)
    assert pictures(stack) == [] and slides(stack) == [] and second.graphicsEffect() is None
    slide_over(stack, first, "normal", back=True)
    assert stack.currentWidget() is first and first.graphicsEffect() is None, "the page under it is live"
    (leaving,) = pictures(stack)
    assert leaving.graphicsEffect().offset == QPoint(), "it slides away from where it was"
    assert len(stack.findChildren(Dim, options=Qt.FindChildOption.FindDirectChildrenOnly)) == 1
    move_on(manual_time, duration(OVER_MS, "extra") + 150)
    assert pictures(stack) == [] and stack.findChildren(Dim) == []
    stack.close()


def test_under_reduce_settings_fades_through_rather_than_over_the_page(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    stack, _first, second = two_pages(qapp)
    slide_over(stack, second, "reduce")
    effect = second.graphicsEffect()
    assert effect.offset == QPoint() and effect.opacity == 0
    assert stack.findChildren(Dim) == []
    move_on(manual_time, duration(OVER_MS, "extra") + 150)
    assert second.graphicsEffect() is None and pictures(stack) == []
    stack.close()


def test_the_page_sliding_in_is_painted_once_not_on_every_frame(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """Settings stuttered in. The page was drawn through an effect, which paints the whole page again
    for each frame. A picture of it slides instead, so the page paints for the picture and when it
    lands, however many frames the slide has."""

    class Counted(QLabel):
        paints = 0

        def paintEvent(self, event: object) -> None:  # noqa: N802
            Counted.paints += 1
            super().paintEvent(event)  # type: ignore[arg-type]

    stack = QStackedWidget()
    first, second = QLabel("Week"), Counted("Settings")
    stack.addWidget(first)
    stack.addWidget(second)
    stack.resize(400, 300)
    stack.show()
    qapp.processEvents()
    Counted.paints = 0
    slide_over(stack, second, "normal")
    frames = 0
    for _ in range((duration(OVER_MS, "normal") + 150) // 8):
        move_on(manual_time, 8)
        frames += 1
    assert frames >= 8, "the slide ran for several frames"
    assert Counted.paints <= 3, f"the page painted {Counted.paints} times over {frames} frames"
    assert stack.currentWidget() is second and second.graphicsEffect() is None
    stack.close()
