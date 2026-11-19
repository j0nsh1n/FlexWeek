"""Short fades and slides that make a change easy to follow (decisions 28 to 35 of 0.17).

Nothing waits for an animation. The new page or week is live at once. A picture of what was there
before fades on top of it, and what comes in is painted faded and a little to one side until it
settles, while the widget itself already sits where it belongs: layouts keep it there and clicks find
it there, so a click is never slower than it was. The student's Animations setting picks the level,
and every design's own motion asks this module how far and how long.
"""

from __future__ import annotations

import contextlib
import weakref
from collections.abc import Callable, Iterable

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QElapsedTimer,
    QEvent,
    QObject,
    QPoint,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsEffect, QLabel, QStackedWidget, QWidget

from desktop.native.motion_level import (  # noqa: F401
    EASE_MS,
    LEVELS,
    Level,
    app_level,
    distance,
    duration,
    frame_interval_ms,
    motion_level,
    moves,
    set_app_level,
)

# Every duration and distance below is Normal's; the level scales it.
# A page changing: the old one fades out steadily and the new one comes in PAGE_IN_AFTER_MS behind it,
# so the window is never empty (Grok Bot's 0.17.0 audit found 3 or 4 blank frames when the new page
# waited for the old one to go, as decision 28 had it).
PAGE_OUT_MS, PAGE_IN_MS, PAGE_IN_AFTER_MS = 120, 160, 30
# How far Day, Week and Month slide as they change, toward the segment chosen. At 12 no slide was seen.
SLIDE_PX = 24
LINEAR = QEasingCurve(QEasingCurve.Type.Linear)
# How far a notice, a sheet, a dialog and Ctrl+K rise as they appear (decision 31).
RISE_PX = 8
# Settings sliding in over the week, and how much the week behind it dims (decision 30).
OVER_MS, OVER_DIM = 200, 0.2
FADE_NAME = "motionFade"
# The picture of a page sliding in over another, as Settings does.
SLIDE_NAME = "motionSlide"
OUT = QEasingCurve(QEasingCurve.Type.OutCubic)


def apply_ui_effects(level: str) -> None:
    """The app's level: Qt's own fades for menus and tooltips, on unless animations are off, its
    sliding dropdown lists only where things may travel, and the level `app_level` gives the rest."""
    set_app_level(level)
    on = duration(EASE_MS) > 0
    for effect in (
        Qt.UIEffect.UI_AnimateMenu,
        Qt.UIEffect.UI_FadeMenu,
        Qt.UIEffect.UI_AnimateTooltip,
        Qt.UIEffect.UI_FadeTooltip,
    ):
        QApplication.setEffectEnabled(effect, on)
    QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, moves())


def screen_rate(widget: QWidget | None) -> float:
    """The refresh rate of the screen `widget` is on, or 0 when Qt cannot say. Called on the class:
    a focus panel keeps a button on `screen`, which would hide the method."""
    if widget is None:
        return 0.0
    screen = QWidget.screen(widget)
    if screen is None:
        return 0.0
    return float(screen.refreshRate())


def _fit_for_picture(widget: QWidget) -> None:
    """Give `widget` the size it will have on screen before a picture is taken of it. A stacked
    page grabbed at its old size is drawn once small, then resized, then drawn again while it
    fades."""
    parent = widget.parentWidget()
    if isinstance(parent, QStackedWidget):
        area = parent.size()
        if area.width() > 0 and area.height() > 0 and widget.size() != area:
            widget.resize(area)
    widget.ensurePolished()
    layout = widget.layout()
    if layout is not None:
        layout.activate()


def _kept(widget: QWidget) -> QPixmap | None:
    """One picture of `widget` as it looks now. A label that already holds a picture gives that,
    rather than drawing it again."""
    if isinstance(widget, QLabel):
        shot = widget.pixmap()
        if not shot.isNull():
            return shot
    shot = widget.grab()
    return None if shot.isNull() else shot


class Shift(QGraphicsEffect):
    """Paints its widget at `opacity`, `offset` pixels from where it is. The widget itself does not
    move, so its layout keeps it in place and a click lands where it will be. `far` is the furthest
    it is ever painted from home, which Qt needs to know to repaint enough. `picture`, when it is
    given, is drawn on each frame instead of asking the widget to paint itself again."""

    def __init__(self, parent: QWidget, far: QPoint, picture: QPixmap | None = None) -> None:
        super().__init__(parent)
        self.opacity = 1.0
        self.offset = QPoint()
        self._far = far
        self._picture = picture if picture is not None and not picture.isNull() else None

    def set(self, opacity: float, offset: QPoint) -> None:
        self.opacity, self.offset = opacity, offset
        self.update()

    def drop_picture(self) -> None:
        """Draw the live widget from now on, so typing or a click is seen during the fade."""
        if self._picture is None:
            return
        self._picture = None
        self.update()

    def boundingRectFor(self, rect: QRectF) -> QRectF:  # noqa: N802
        return rect.united(rect.translated(self._far))

    def draw(self, painter: QPainter) -> None:
        if self.opacity <= 0:
            return
        if self.opacity >= 1 and self.offset.isNull():
            self.drawSource(painter)
            return
        painter.save()
        painter.setOpacity(painter.opacity() * self.opacity)
        if self._picture is not None:
            painter.drawPixmap(self.offset, self._picture)
        else:
            system = Qt.CoordinateSystem.LogicalCoordinates
            pixmap = self.sourcePixmap(system, QPoint(), QGraphicsEffect.PixmapPadMode.NoPad)
            origin = self.sourceBoundingRect(system).topLeft().toPoint()
            painter.drawPixmap(origin + self.offset, pixmap)
        painter.restore()


_started = QElapsedTimer()
_started.start()


def now_ms() -> int:
    """The time every Clock reads, in milliseconds from any fixed start. Tests put their own over this
    name, so an animation can be moved to an exact moment instead of waited for."""
    return int(_started.elapsed())


# Every clock still running, so slow work can wait until nothing is moving.
_RUNNING: weakref.WeakSet[Clock] = weakref.WeakSet()


def busy() -> bool:
    """Whether any animation is running now on a widget that is on screen."""
    for clock in list(_RUNNING):
        try:
            state = clock.state()
            if state == QAbstractAnimation.State.Stopped:
                _RUNNING.discard(clock)
                continue
            if state == QAbstractAnimation.State.Paused:
                continue
            parent = clock.parent()
            if isinstance(parent, QWidget) and not parent.isVisible():
                continue
            return True
        except RuntimeError:
            _RUNNING.discard(clock)
    return False


def _forget_clock(clock: Clock) -> Callable[..., None]:
    ref = weakref.ref(clock)

    def forget(*_: object) -> None:
        if (gone := ref()) is not None:
            _RUNNING.discard(gone)

    return forget


class Clock(QObject):
    """A frame clock for one animation. Qt's own animation clock stays near 60 Hz, and this PySide
    has no way to replace it, so a precise timer follows the screen. The time it reports is how long
    the animation has been running, so a late frame still lands on the right part of the easing."""

    finished = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._total = 0
        self._step: Callable[[float], None] | None = None
        self._base = 0
        self._stopped = False
        self._done = False
        self._paused = False
        # When this stretch of the animation began on now_ms's time; None before it first starts.
        self._since: int | None = None
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        # Not a bound method of this clock: Qt skips a slot whose receiver is the object being destroyed,
        # so a clock deleted under its widget stayed in _RUNNING with its timer gone.
        self.destroyed.connect(_forget_clock(self))

    def start(self, total: int, step: Callable[[float], None]) -> None:
        self._total = total
        self._step = step
        self._base = 0
        self._stopped = False
        self._done = False
        self._paused = False
        self._since = now_ms()
        self._retarget()
        _RUNNING.add(self)
        self._timer.start()

    def stop(self) -> None:
        self._stopped = True
        self._paused = False
        self._timer.stop()
        _RUNNING.discard(self)

    def pause(self) -> None:
        if self._paused or self._done or self._stopped or not self._timer.isActive():
            return
        self._base += self._gone()
        self._paused = True
        self._timer.stop()

    def resume(self) -> None:
        if not self._paused or self._done or self._stopped:
            return
        self._paused = False
        self._since = now_ms()
        self._timer.start()

    def duration(self) -> int:
        return self._total

    def currentTime(self) -> int:  # noqa: N802
        if self._paused or self._since is None:
            return min(self._base, self._total)
        return min(self._base + self._gone(), self._total)

    def state(self) -> QAbstractAnimation.State:
        if self._paused:
            return QAbstractAnimation.State.Paused
        if self._timer.isActive():
            return QAbstractAnimation.State.Running
        return QAbstractAnimation.State.Stopped

    def setCurrentTime(self, ms: int) -> None:  # noqa: N802
        """Jump to `ms` milliseconds in, and finish when that is the end."""
        self._base = ms
        self._since = now_ms()
        self._apply(self._base)

    def interval(self) -> int:
        return self._timer.interval()

    def _gone(self) -> int:
        return 0 if self._since is None else now_ms() - self._since

    def _retarget(self) -> None:
        parent = self.parent()
        gap = frame_interval_ms(screen_rate(parent if isinstance(parent, QWidget) else None))
        if self._timer.interval() != gap:
            self._timer.setInterval(gap)

    def _tick(self) -> None:
        if self._stopped or self._done:
            return
        self._retarget()
        self._apply(self._base + self._gone())

    def _apply(self, ms: int) -> None:
        if self._done or self._step is None:
            return
        if ms >= self._total:
            self._done = True
            self._timer.stop()
            _RUNNING.discard(self)
            self._step(float(self._total))
            self.finished.emit()
            return
        self._step(float(ms))


class Dim(QWidget):
    """Black laid over what is under it at `share` of OVER_DIM, letting the pointer through."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.share = 0.0

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, round(255 * OVER_DIM * self.share)))
        painter.end()


def settle(widget: QWidget) -> None:
    """End an animation still running on `widget` where it would have ended, so a second one starts
    from where the widget belongs. Stopping one does not emit `finished`, so its tidying runs here."""
    kick = getattr(widget, "_motion_live", None)
    if kick is not None:
        kick.detach()
        widget._motion_live = None  # type: ignore[attr-defined]
    running = getattr(widget, "_motion_running", None)
    widget._motion_running = None  # type: ignore[attr-defined]
    if running is None:
        return
    animation, done = running
    with contextlib.suppress(RuntimeError):
        animation.finished.disconnect(done)
        animation.stop()
    done()
    with contextlib.suppress(RuntimeError):
        animation.deleteLater()


def _run(owner: QWidget, total: int, step: Callable[[float], None], done: Callable[[], None]) -> None:
    """Call `step` with the milliseconds gone, from 0 to `total`, each frame, then `done`. The first
    call is immediate, so the fade is on screen before the first interval. The clock belongs to
    `owner`, and `settle(owner)` ends it early."""
    if total <= 0:
        done()
        return
    step(0.0)
    clock = Clock(owner)

    def finish() -> None:
        owner._motion_running = None  # type: ignore[attr-defined]
        done()
        with contextlib.suppress(RuntimeError):
            clock.deleteLater()

    clock.finished.connect(finish)
    owner._motion_running = (clock, finish)  # type: ignore[attr-defined]
    clock.start(total, step)




def _along(at: float, wait: int, length: int) -> float:
    """How far along, eased, is something that starts `wait` milliseconds in and takes `length`."""
    if at < wait:
        return 0.0
    return OUT.valueForProgress((at - wait) / length) if length else 1.0


def clear_fades(host: QWidget) -> None:
    """Drop pictures still fading over `host`, and dimming left from Settings sliding away, so a new
    picture never captures an old one."""
    direct = Qt.FindChildOption.FindDirectChildrenOnly
    for leftover in (
        *host.findChildren(QLabel, FADE_NAME, direct),
        *host.findChildren(QLabel, SLIDE_NAME, direct),
        *host.findChildren(Dim, options=direct),
    ):
        leftover.hide()
        leftover.deleteLater()




def hold_picture(
    host: QWidget, level: str, area: QRect | None = None, *, beside: bool = False
) -> QLabel | None:
    """A picture of `host`, or of `area` of it, as it looks now, laid over it until it is let go.
    None when nothing would fade. `beside` is a second picture of the same change, which keeps the
    first rather than clearing it as a stale one."""
    if duration(EASE_MS, level) == 0 or not host.isVisible() or host.width() <= 0 or host.height() <= 0:
        return None
    if not beside:
        clear_fades(host)
    shown = area if area is not None else host.rect()
    picture = QLabel(host)
    picture.setObjectName(FADE_NAME)
    picture.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    picture.setPixmap(host.grab(shown))
    picture.setGeometry(shown)
    picture.show()
    picture.raise_()
    return picture




def fade_away(
    picture: QLabel | None, level: str, *, ms: int = EASE_MS, drift: int = 0, steady: bool = False
) -> None:
    """Fade `picture` out in Normal's `ms`, drifting `drift` of Normal's pixels sideways (to the left
    when negative) where things may travel, then delete it. `steady` fades it at an even pace rather
    than fast first, for a page whose successor is still coming in under it."""
    if picture is None:
        return
    length = duration(ms, level)
    if length == 0:
        picture.deleteLater()
        return
    end = QPoint(distance(drift, level), 0)
    effect = Shift(picture, end, _kept(picture))
    picture.setGraphicsEffect(effect)
    fading = LINEAR if steady else OUT

    def step(at: float) -> None:
        share = fading.valueForProgress(at / length)
        effect.set(1 - share, end * share)

    _run(picture, length, step, picture.deleteLater)


class _LiveOnInput(QObject):
    """The first key or click on `widget` drops its fade picture so the live widget shows through."""

    def __init__(self, effect: Shift, widget: QWidget) -> None:
        super().__init__(widget)
        self._effect = effect
        self._widget = widget
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() not in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress):
            return False
        if not isinstance(watched, QWidget):
            return False
        if watched is self._widget or self._widget.isAncestorOf(watched):
            self._effect.drop_picture()
            self.detach()
        return False

    def detach(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)


def appear(
    widget: QWidget,
    level: str,
    *,
    rise: bool = False,
    shift: int = 0,
    delay_ms: int = 0,
    ms: int = EASE_MS,
    grow: bool = False,
) -> None:
    """Fade `widget` in where it already is. A notice or a sheet can rise into place, and a page can
    come in from `shift` pixels to the side. `delay_ms` keeps it unseen first, to follow the page
    before it out or to stagger a list. All in Normal's pixels and milliseconds. A window's insides
    have nothing under them to fade over, so a dialog fades its content, not itself. `grow` is for
    a widget a layout has just made room for: where things may travel its height opens from nothing,
    so what the layout puts below it moves with it rather than jumping."""
    settle(widget)
    wait, length = duration(delay_ms, level), duration(ms, level)
    if wait + length == 0 or not widget.isVisible():
        return
    start = QPoint(distance(shift, level), distance(RISE_PX, level) if rise else 0)
    live = grow and moves(level)
    if not live:
        _fit_for_picture(widget)
    # Growing changes the widget's height on every frame, so that one has to be drawn live. Anything
    # else is painted once and the picture moves.
    effect = Shift(widget, start, None if live else _kept(widget))
    widget.setGraphicsEffect(effect)
    kick = None if live else _LiveOnInput(effect, widget)
    widget._motion_live = kick  # type: ignore[attr-defined]
    full = widget.sizeHint().height() if live else 0
    limit = widget.maximumHeight()

    def step(at: float) -> None:
        share = _along(at, wait, length)
        effect.set(share, start * (1 - share))
        if full:
            widget.setMaximumHeight(round(full * share))

    def done() -> None:
        if kick is not None:
            kick.detach()
        widget._motion_live = None  # type: ignore[attr-defined]
        # An effect left in place makes every later repaint of the widget go through it.
        widget.setGraphicsEffect(None)
        widget.setMaximumHeight(limit)

    _run(widget, wait + length, step, done)


def fade_through(picture: QLabel | None, incoming: Iterable[QWidget], level: str, direction: int = 0) -> None:
    """The picture of what was there out and what replaced it in: the old fades steadily in
    PAGE_OUT_MS and each of `incoming` comes in over PAGE_IN_MS, PAGE_IN_AFTER_MS behind it, so the
    window is never empty and the two are only seen together faintly and briefly. With a `direction`
    (1 forward, -1 back) the old drifts away from it and the new slides in from its side, so the two
    are moving apart while both show."""
    if picture is None:
        return
    fade_away(picture, level, ms=PAGE_OUT_MS, drift=-direction * SLIDE_PX, steady=True)
    for widget in incoming:
        appear(widget, level, shift=direction * SLIDE_PX, delay_ms=PAGE_IN_AFTER_MS, ms=PAGE_IN_MS)


def switch_page(stack: QStackedWidget, page: QWidget, level: str, direction: int = 0) -> None:
    """Show `page` at once, the page it replaces fading through to it."""
    if stack.currentWidget() is page:
        return
    # A page still on its way in is taken as it will be, not half faded.
    settle(stack.currentWidget())
    picture = hold_picture(stack, level)
    stack.setCurrentWidget(page)
    fade_through(picture, [page], level, direction)
