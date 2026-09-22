"""Short fades and slides that make a change easy to follow.

Nothing waits for an animation. The new page or week is live at once, and only a picture of what was
there before fades away on top of it, so a click is never slower than it was. The student's
Animations setting picks the level, and Off turns every one of them off.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QStackedWidget, QWidget

LEVELS = ("off", "normal", "extra")
# Long enough to see where things went, short enough never to feel like waiting.
DURATION_MS = {"off": 0, "normal": 180, "extra": 260}
# How far a picture of the old week drifts as it fades, in the direction the student moved.
DRIFT_PX = {"off": 0, "normal": 16, "extra": 32}
# How far a notice rises as it appears.
RISE_PX = {"off": 0, "normal": 8, "extra": 14}
FADE_NAME = "motionFade"


def motion_level(preference: object, look_default: object) -> str:
    """The student's Animations setting, or the look's own when they never chose one."""
    if preference in LEVELS:
        return str(preference)
    return str(look_default) if look_default in LEVELS else "normal"


def apply_ui_effects(level: str) -> None:
    """Qt's own fades for menus, dropdown lists and tooltips, on unless animations are off."""
    on = level != "off"
    for effect in (
        Qt.UIEffect.UI_AnimateMenu,
        Qt.UIEffect.UI_FadeMenu,
        Qt.UIEffect.UI_AnimateCombo,
        Qt.UIEffect.UI_AnimateTooltip,
        Qt.UIEffect.UI_FadeTooltip,
    ):
        QApplication.setEffectEnabled(effect, on)


def clear_fades(host: QWidget) -> None:
    """Drop pictures still fading over `host`, so a new one never captures an old one."""
    for picture in host.findChildren(QLabel, FADE_NAME, Qt.FindChildOption.FindDirectChildrenOnly):
        picture.hide()
        picture.deleteLater()


def hold_picture(host: QWidget, level: str) -> QLabel | None:
    """A picture of `host` as it looks now, laid over it until `fade_away` lets it go."""
    if DURATION_MS.get(level, 0) == 0 or not host.isVisible() or host.width() <= 0 or host.height() <= 0:
        return None
    clear_fades(host)
    picture = QLabel(host)
    picture.setObjectName(FADE_NAME)
    picture.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    picture.setPixmap(host.grab())
    picture.setGeometry(host.rect())
    picture.show()
    picture.raise_()
    return picture


def fade_away(picture: QLabel | None, level: str, direction: int = 0) -> None:
    """Fade `picture` out, drifting it by `direction` (-1 left, 1 right, 0 still), then delete it."""
    if picture is None:
        return
    duration = DURATION_MS.get(level, 0)
    if duration == 0:
        picture.deleteLater()
        return
    effect = QGraphicsOpacityEffect(picture)
    picture.setGraphicsEffect(effect)
    group = QParallelAnimationGroup(picture)
    fade = QPropertyAnimation(effect, b"opacity", group)
    fade.setDuration(duration)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    group.addAnimation(fade)
    if direction:
        slide = QPropertyAnimation(picture, b"pos", group)
        slide.setDuration(duration)
        slide.setStartValue(picture.pos())
        slide.setEndValue(picture.pos() + QPoint(direction * DRIFT_PX[level], 0))
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(slide)
    group.finished.connect(picture.deleteLater)
    group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def switch_page(stack: QStackedWidget, page: QWidget, level: str) -> None:
    """Show `page` at once and fade the page it replaces away above it."""
    if stack.currentWidget() is page:
        return
    picture = hold_picture(stack, level)
    stack.setCurrentWidget(page)
    fade_away(picture, level)


def appear(widget: QWidget, level: str, *, rise: bool = False) -> None:
    """Fade `widget` in where it already is. A free-floating widget can also rise into place."""
    duration = DURATION_MS.get(level, 0)
    if duration == 0 or not widget.isVisible():
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    group = QParallelAnimationGroup(widget)
    fade = QPropertyAnimation(effect, b"opacity", group)
    fade.setDuration(duration)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    group.addAnimation(fade)
    if rise:
        end = widget.pos()
        slide = QPropertyAnimation(widget, b"pos", group)
        slide.setDuration(duration)
        slide.setStartValue(end + QPoint(0, RISE_PX[level]))
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(slide)
    # An opacity effect left in place makes every later repaint of the widget go through it.
    group.finished.connect(lambda: widget.setGraphicsEffect(None))
    group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def vanish(widget: QWidget, level: str) -> None:
    """Fade `widget` out, then hide it."""
    duration = DURATION_MS.get(level, 0)
    if duration == 0 or not widget.isVisible():
        widget.hide()
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(duration)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    fade.setEasingCurve(QEasingCurve.Type.InCubic)

    def done() -> None:
        widget.hide()
        widget.setGraphicsEffect(None)

    fade.finished.connect(done)
    fade.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
