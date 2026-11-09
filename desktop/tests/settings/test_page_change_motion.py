"""Motion never delays a click: the new page is live at once, only a picture of the old one fades, and
what comes in is painted on its way while the widget already sits where it belongs."""

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
    from PySide6.QtGui import QColor, QPalette, QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QStackedWidget, QVBoxLayout, QWidget

    from desktop.native.motion import (
        PAGE_IN_AFTER_MS,
        PAGE_IN_MS,
        appear,
        apply_ui_effects,
        duration,
        hold_picture,
        switch_page,
    )
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.settings.support_motion import THROUGH_MS, move_on, pictures, two_pages
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


def test_a_switch_is_immediate_and_its_fade_clears_itself(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, "normal")
    assert stack.currentWidget() is second, "the new page is live before any animation"
    assert len(pictures(stack)) == 1
    move_on(manual_time, THROUGH_MS)
    assert pictures(stack) == []
    stack.close()


@pytest.mark.parametrize("level", ["normal", "extra", "reduce"])
def test_a_switch_never_shows_an_empty_page(
    qapp: QApplication, manual_time: ManualTime, level: str  # noqa: F811
) -> None:
    """When the new page waited for the old one to go, the window dipped through 3 or 4 almost blank
    frames. Now the new page comes in while the old one is still going: together they are never less
    than three quarters there, and the old one is half gone before the new one is half there, so the
    two are only seen together faintly."""
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, level)
    frames: list[tuple[float, float]] = []
    for _ in range(THROUGH_MS // 4 + 1):
        old, new = pictures(stack), second.graphicsEffect()
        going = max((picture.graphicsEffect().opacity for picture in old), default=0.0)
        frames.append((going, new.opacity if new else 1.0))
        if not old and new is None:
            break
        move_on(manual_time, 4)
    else:
        raise AssertionError("an effect left in place slows every later repaint")
    assert frames[0] == (1.0, 0.0), "it starts from the old page"
    assert min(old + new for old, new in frames) >= 0.7, "never an empty page"
    assert any(0 < old < 1 and 0 < new < 1 for old, new in frames), "the new one comes in as the old goes"
    assert all(old <= 0.5 for old, new in frames if new >= 0.5), "the old is half gone by the time"
    stack.close()


def test_off_means_a_switch_has_no_picture(qapp: QApplication) -> None:  # noqa: F811
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, "off")
    assert stack.currentWidget() is second
    assert pictures(stack) == []
    stack.close()


def test_quick_switches_never_stack_pictures(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """A picture taken over a fading one would show the page before last."""
    stack, first, second = two_pages(qapp)
    switch_page(stack, second, "extra")
    switch_page(stack, first, "extra")
    qapp.processEvents()
    assert len(pictures(stack)) == 1
    move_on(manual_time, THROUGH_MS)
    assert pictures(stack) == []
    assert (first.graphicsEffect(), second.graphicsEffect()) == (None, None)
    stack.close()


def test_a_page_slides_in_from_the_side_it_is_heading_and_lands_in_place(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, "normal", 1)
    assert stack.currentWidget() is second, "the new page is live before any animation"
    assert second.graphicsEffect().offset == QPoint(24, 0), "going forward, it comes in from the right"
    assert second.pos().isNull(), "painted to the side: the page itself is where clicks find it"
    manual_time.advance(40)
    (old,) = pictures(stack)
    # The old page fades evenly over 120 ms and drifts 24 pixels left: a third of the way at 40 ms.
    assert old.graphicsEffect().offset == QPoint(-8, 0), "the old page drifts away to the left"
    assert old.graphicsEffect().opacity == pytest.approx(2 / 3)
    # The new one starts 30 ms behind and takes 160, out-cubic: 10/160 in, 1 - (15/16)^3 of the way.
    assert second.graphicsEffect().opacity == pytest.approx(1 - (15 / 16) ** 3)
    assert second.graphicsEffect().offset == QPoint(20, 0)
    move_on(manual_time, THROUGH_MS)
    assert second.pos().isNull()
    assert second.graphicsEffect() is None
    assert pictures(stack) == []
    stack.close()


def test_under_reduce_a_page_fades_through_and_moves_nothing(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, "reduce", 1)
    effect = second.graphicsEffect()
    assert effect.offset == QPoint() and effect.opacity == 0, "no slide, and still a fade"
    manual_time.advance(40)
    (old,) = pictures(stack)
    assert old.graphicsEffect().offset == QPoint(), "no drift"
    assert old.graphicsEffect().opacity == pytest.approx(2 / 3), "a third of 120 ms gone"
    move_on(manual_time, THROUGH_MS)
    assert pictures(stack) == [] and second.graphicsEffect() is None
    stack.close()


class _Counted(QWidget):
    """A child whose paints can be counted. A page drawn through an effect paints these every frame."""

    def __init__(self) -> None:
        super().__init__()
        self.paints = 0
        self.setMinimumHeight(24)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        self.paints += 1


def test_a_page_change_does_not_repaint_the_live_page_every_frame(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """The page coming in is live at once. Its widgets are painted into one picture for the fade,
    not again on every frame."""
    apply_ui_effects("normal")
    stack = QStackedWidget()
    first = QLabel("Week")
    second = QWidget()
    column = QVBoxLayout(second)
    children = [_Counted() for _ in range(6)]
    for child in children:
        column.addWidget(child)
    stack.addWidget(first)
    stack.addWidget(second)
    stack.resize(400, 300)
    stack.show()
    qapp.processEvents()
    for child in children:
        child.paints = 0
    switch_page(stack, second, "normal")
    length = duration(PAGE_IN_AFTER_MS + PAGE_IN_MS, "normal") + 80
    frames = 0
    for _ in range(length // 8):
        move_on(manual_time, 8)
        frames += 1
    assert frames >= 8, "the page change ran for several frames"
    for child in children:
        assert child.paints <= 3, f"a live widget painted {child.paints} times over {frames} frames"
    stack.close()


def test_a_page_change_ends_where_motion_off_leaves_it(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """The fade is only on the way. Where it ends is the page motion Off shows at once: no effect on
    the page, no picture left over, the page at its place."""

    def lands_clean(level: str) -> None:
        apply_ui_effects(level)
        stack, _first, second = two_pages(qapp)
        switch_page(stack, second, level)
        move_on(manual_time, THROUGH_MS)
        assert second.graphicsEffect() is None and pictures(stack) == []
        assert second.pos() == QPoint(0, 0)
        stack.close()

    lands_clean("normal")
    lands_clean("off")


def test_a_page_is_pictured_at_the_size_it_will_have_on_screen(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A stacked page grabbed at its old size is drawn once small, then resized and drawn again
    while it fades. The picture is taken after it has the stack's size."""
    from desktop.native import motion as moving

    apply_ui_effects("normal")
    stack = QStackedWidget()
    first = QLabel("Week")
    second = QWidget()
    QVBoxLayout(second).addWidget(QLabel("Day"))
    stack.addWidget(first)
    stack.addWidget(second)
    stack.resize(640, 400)
    stack.show()
    qapp.processEvents()
    stack.setCurrentWidget(second)
    qapp.processEvents()
    # Stale size, as a newly shown view can still have until its layout runs.
    second.resize(80, 40)
    sizes: list[tuple[int, int]] = []
    real = moving._kept

    def spy(widget: QWidget) -> QPixmap | None:
        sizes.append((widget.width(), widget.height()))
        return real(widget)

    monkeypatch.setattr(moving, "_kept", spy)
    appear(second, "normal")
    assert sizes, "the incoming page was pictured"
    assert sizes[0] == (stack.width(), stack.height()), sizes
    stack.close()


def test_a_click_in_a_fade_drops_its_picture_but_another_windows_key_does_not(
    qapp: QApplication,  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    owner = QWidget()
    field = QLineEdit(owner)
    owner.resize(200, 80)
    owner.show()
    other = QLineEdit()
    other.show()
    qapp.processEvents()
    appear(owner, "normal")
    effect = owner.graphicsEffect()
    assert effect._picture is not None
    QTest.keyClicks(other, "Elsewhere")
    assert other.text() == "Elsewhere"
    assert effect._picture is not None, "input in another window must not end this picture"
    QTest.mouseClick(field, Qt.MouseButton.LeftButton)
    assert effect._picture is None, "a click inside the fade shows its live contents"
    owner.close()
    other.close()


def test_a_fade_picture_shows_the_week_as_it_is_after_a_block_is_added(qapp: QApplication) -> None:  # noqa: F811
    """A reused grab must not keep a picture from before the week changed. The picture's pixel is a
    probe that it is a fresh grab, not a check of how the block looks."""
    apply_ui_effects("normal")
    week = QWidget()
    week.setAutoFillBackground(True)
    palette = week.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#111111"))
    week.setPalette(palette)
    week.resize(200, 120)
    week.show()
    qapp.processEvents()
    stale = hold_picture(week, "normal")
    assert stale is not None
    stale.hide()
    stale.deleteLater()
    qapp.processEvents()
    block = QWidget(week)
    block.setGeometry(24, 24, 48, 48)
    block.setAutoFillBackground(True)
    ink = block.palette()
    ink.setColor(QPalette.ColorRole.Window, QColor("#ff00aa"))
    block.setPalette(ink)
    block.show()
    qapp.processEvents()
    picture = hold_picture(week, "normal")
    assert picture is not None
    sample = picture.pixmap().toImage().pixelColor(48, 48)
    assert sample.name() == "#ff00aa", "the fade shows the block, not the empty week"
    week.close()
