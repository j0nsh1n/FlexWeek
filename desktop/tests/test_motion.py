"""Motion never delays a click: the new page is live at once, and only a picture of the old one fades."""

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
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget, QWidget

    from desktop.native.motion import DURATION_MS, FADE_NAME, appear, motion_level, switch_page


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-motion-test"])


def pictures(host: QWidget) -> list[QLabel]:
    return [label for label in host.findChildren(QLabel, FADE_NAME) if label.isVisible()]


def two_pages(qapp: QApplication) -> tuple[QStackedWidget, QWidget, QWidget]:
    stack = QStackedWidget()
    first, second = QLabel("Week"), QLabel("Month")
    stack.addWidget(first)
    stack.addWidget(second)
    stack.resize(400, 300)
    stack.show()
    qapp.processEvents()
    return stack, first, second


@pytest.mark.parametrize(
    ("preference", "look", "level"),
    [("off", "extra", "off"), (None, "extra", "extra"), (None, None, "normal"), ("fast", "normal", "normal")],
)
def test_the_students_setting_wins_over_the_looks_own(preference: object, look: object, level: str) -> None:
    assert motion_level(preference, look) == level


def test_a_switch_is_immediate_and_its_fade_clears_itself(qapp: QApplication) -> None:
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, "normal")
    assert stack.currentWidget() is second, "the new page is live before any animation"
    assert len(pictures(stack)) == 1
    QTest.qWait(DURATION_MS["normal"] + 150)
    assert pictures(stack) == []
    stack.close()


def test_off_means_no_animation(qapp: QApplication) -> None:
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, "off")
    assert stack.currentWidget() is second
    assert pictures(stack) == []
    stack.close()


def test_quick_switches_never_stack_pictures(qapp: QApplication) -> None:
    """A picture taken over a fading one would show the page before last."""
    stack, first, second = two_pages(qapp)
    switch_page(stack, second, "extra")
    switch_page(stack, first, "extra")
    qapp.processEvents()
    assert len(pictures(stack)) == 1
    QTest.qWait(DURATION_MS["extra"] + 150)
    assert pictures(stack) == []
    stack.close()


def test_a_notice_rises_into_place_and_leaves_no_effect_behind(qapp: QApplication) -> None:
    host = QWidget()
    host.resize(400, 300)
    notice = QLabel("Saved.", host)
    notice.move(40, 60)
    host.show()
    qapp.processEvents()
    appear(notice, "normal", rise=True)
    assert notice.graphicsEffect() is not None
    QTest.qWait(DURATION_MS["normal"] + 150)
    assert (notice.x(), notice.y()) == (40, 60)
    assert notice.graphicsEffect() is None, "an effect left in place slows every later repaint"
    host.close()
