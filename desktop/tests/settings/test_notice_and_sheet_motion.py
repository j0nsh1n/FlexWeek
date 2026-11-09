"""Notices rise into place, dialogs and sheets fade in through their content, the plan bar slides down
over the planner, and a marker glides: each ends where it belongs and leaves no effect behind."""

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
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QGraphicsDropShadowEffect,
        QLabel,
        QLineEdit,
        QVBoxLayout,
        QWidget,
    )

    from desktop.native.motion import (
        EASE_MS,
        RISE_PX,
        appear,
        apply_ui_effects,
        duration,
        glide,
        slide_down,
    )
    from desktop.native.widgets import TOAST_FOOT, Dialog, PlanReview, Toast
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.settings.support_motion import move_on
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


def test_a_notice_that_arrives_while_the_last_one_rises_lands_where_it_belongs(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """The hours a notice floats over can move while one rises, as large text grows the bar. A rise
    still running from the last notice carried the new one back to where the last was meant to go."""
    host = QWidget()
    host.resize(600, 400)
    hours = QWidget(host)
    hours.setGeometry(0, 60, 600, 300)
    toast = Toast(host, hours)
    toast.motion = "extra"
    host.show()
    qapp.processEvents()
    toast.show_message("Moved History essay to Fri 18:00.")
    manual_time.advance(30)
    hours.setGeometry(0, 72, 600, 280)
    toast.show_message("Running late: 16:30-17:00 is now locked.")
    manual_time.advance(duration(EASE_MS, "extra"))
    # The card, inside the room the toast keeps round it for its shadow.
    assert toast.y() + toast.card.geometry().bottom() + 1 == 72 + 280 - TOAST_FOOT
    host.close()


def test_a_glide_ends_on_its_target(qapp: QApplication, manual_time: ManualTime) -> None:  # noqa: F811
    host = QWidget()
    host.resize(200, 300)
    marker = QFrame(host)
    marker.setGeometry(QRect(10, 10, 3, 20))
    host.show()
    qapp.processEvents()
    glide(marker, QRect(10, 120, 3, 24), "normal")
    manual_time.advance(40)
    # 40 of the 280 ms shared glide (the 220 ms planning ease plus 60) on the out-cubic curve:
    # 1 - (6/7)^3 of the way. Qt rounds each edge half away from zero: y 50.73 -> 51, height 21.48 -> 21.
    assert marker.geometry() == QRect(10, 51, 3, 21), "it moves there rather than jumping"
    glide(marker, QRect(10, 200, 3, 24), "normal")
    manual_time.advance(duration(EASE_MS + 60, "normal"))
    assert marker.geometry() == QRect(10, 200, 3, 24)
    glide(marker, QRect(10, 40, 3, 24), "off")
    assert marker.geometry() == QRect(10, 40, 3, 24), "with animations off it is simply there"
    glide(marker, QRect(10, 90, 3, 24), "reduce")
    assert marker.geometry() == QRect(10, 90, 3, 24), "under Reduce it does not travel either"
    host.close()


def test_a_dialog_fades_and_rises_through_its_content_once(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """A window's own opacity is ignored on Wayland, so dialogs appeared in one frame there. What the
    dialog holds fades and rises instead; the window is never faded."""
    apply_ui_effects("normal")
    dialog = Dialog()
    words = QLabel("Are you sure?")
    # Named, as most of a dialog's parts are: a search for unnamed children found none of them.
    words.setObjectName("question")
    QVBoxLayout(dialog).addWidget(words)
    dialog.resize(300, 200)
    dialog.show()
    effect = words.graphicsEffect()
    assert effect is not None and effect.offset == QPoint(0, RISE_PX)
    manual_time.advance(40)
    # 40 of the 220 ms planning ease on the out-cubic curve: 1 - (1 - 2/11)^3.
    assert effect.opacity == pytest.approx(1 - (9 / 11) ** 3)
    assert dialog.windowOpacity() == 1.0
    manual_time.advance(duration(EASE_MS) - 40)
    assert words.graphicsEffect() is None
    dialog.hide()
    dialog.show()
    assert words.graphicsEffect() is None, "shown again, it is simply there"
    dialog.close()


def a_sheet_over_a_window(qapp: QApplication, *children: QWidget) -> tuple[QWidget, Dialog]:  # noqa: F811
    apply_ui_effects("normal")
    window = QWidget()
    window.resize(900, 700)
    window.show()
    qapp.processEvents()
    sheet = Dialog(window, sheet=True)
    body = sheet.card_body("Add homework")
    for child in children or (QLabel("Homework"),):
        body.addWidget(child)
    sheet.show()
    qapp.processEvents()
    return window, sheet


def test_a_sheet_fades_its_card_and_shadow_as_one_and_keeps_the_shadow(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    window, sheet = a_sheet_over_a_window(qapp)
    shadow = sheet.card.graphicsEffect()
    assert isinstance(shadow, QGraphicsDropShadowEffect)
    face = sheet.card.parentWidget()
    assert face is not sheet and face.graphicsEffect() is not None, "the card and its shadow fade together"
    shade = window.findChild(QWidget, "sheetShade")
    assert 0.0 <= shade.dim_progress < 1.0, "the dim does not jump to full strength at once"
    assert shade.fading, "the dimming comes in with it"
    move_on(manual_time, duration(EASE_MS) + 150)
    assert face.graphicsEffect() is None and not shade.fading
    assert sheet.card.graphicsEffect() is shadow, "the fade leaves the card's shadow alone"
    sheet.close()
    window.close()


def test_typing_during_a_sheet_fade_shows_at_once(qapp: QApplication) -> None:  # noqa: F811
    """While a sheet fades, the title field already has focus. Letters typed then must show, not wait
    under a still picture until the fade ends."""
    field = QLineEdit()
    window, sheet = a_sheet_over_a_window(qapp, field)
    face = sheet._face
    assert face is not None
    effect = face.graphicsEffect()
    assert effect is not None and getattr(effect, "_picture", None) is not None
    field.setFocus()
    QTest.keyClicks(field, "Math")
    assert field.text() == "Math"
    assert getattr(effect, "_picture", "missing") is None, "the still picture gave way so the letters show"
    sheet.close()
    window.close()


class _Counted(QWidget):
    """A child whose paints can be counted. A page drawn through an effect paints these every frame."""

    def __init__(self) -> None:
        super().__init__()
        self.paints = 0
        self.setMinimumHeight(24)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        self.paints += 1


def test_a_sheet_does_not_repaint_the_page_under_it_every_frame(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """The opaque shade holds one picture while page widgets remain live and do not repaint each frame."""
    apply_ui_effects("normal")
    window = QWidget()
    column = QVBoxLayout(window)
    children = [_Counted() for _ in range(6)]
    for child in children:
        column.addWidget(child)
    window.resize(900, 700)
    window.show()
    qapp.processEvents()
    for child in children:
        child.paints = 0
    sheet = Dialog(window, sheet=True)
    sheet.card_body("Add homework").addWidget(QLabel("Homework"))
    sheet.show()
    qapp.processEvents()
    assert all(child.updatesEnabled() for child in children), "the page is not frozen under the shade"
    frames = 0
    for _ in range((duration(EASE_MS, "normal") + 80) // 8):
        move_on(manual_time, 8)
        frames += 1
    assert frames >= 8, "the sheet ran for several frames"
    for child in children:
        assert child.paints <= 4, f"the page painted {child.paints} times over {frames} frames"
    assert all(child.updatesEnabled() for child in children)
    sheet.close()
    window.close()


def opening_review(qapp: QApplication, level: str) -> tuple[QWidget, PlanReview, QWidget]:  # noqa: F811
    from desktop.tests.test_plan_review import TITLES, TRACE, WEEK

    host = QWidget()
    column = QVBoxLayout(host)
    review = PlanReview(host)
    below = QLabel("The page below", host)
    column.addWidget(review)
    column.addWidget(below)
    column.addStretch(1)
    host.resize(500, 400)
    host.show()
    qapp.processEvents()
    review.set_trace(TRACE, TITLES, WEEK, (2, 1))
    slide_down(review, level)
    return host, review, below


def test_the_plan_review_slides_down_over_the_planner_without_pushing_it(
    qapp: QApplication, manual_time: ManualTime  # noqa: F811
) -> None:
    """The bar grew in the column, so Got it was a grey strip for a frame and the week jumped."""
    host = QWidget()
    host.resize(500, 400)
    planner = QLabel("Week hours", host)
    planner.setGeometry(0, 120, 500, 280)
    review = PlanReview(host)
    review.set_trace(
        {"unplaced": [], "moves": [], "explanations": []},
        {},
        "2026-01-05",
        (2, 0),
    )
    review.setGeometry(0, 40, 500, review.sizeHint().height())
    host.show()
    qapp.processEvents()
    before = planner.y()
    slide_down(review, "normal")
    qapp.processEvents()
    assert planner.y() == before, "the planner stays put while the bar moves over it"
    assert review.height() == review.sizeHint().height(), "the bar is drawn at full height from the start"
    move_on(manual_time, duration(EASE_MS, "normal") + 100)
    assert planner.y() == before
    host.close()


def test_the_plan_review_opened_again_before_it_finished_still_ends_free(qapp: QApplication) -> None:  # noqa: F811
    host, review, _below = opening_review(qapp, "normal")
    review._motion_running[0].setCurrentTime(40)
    slide_down(review, "normal")
    review._motion_running[0].setCurrentTime(duration(EASE_MS, "normal"))
    assert review.maximumHeight() == 16777215
    host.close()


@pytest.mark.parametrize("level", ["reduce", "off"])
def test_where_nothing_travels_the_plan_review_is_full_height_at_once(
    qapp: QApplication, level: str  # noqa: F811
) -> None:
    host, review, _below = opening_review(qapp, level)
    assert review.maximumHeight() == 16777215
    qapp.processEvents()
    assert review.height() == review.sizeHint().height()
    host.close()
