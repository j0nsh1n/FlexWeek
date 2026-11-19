"""What the Widgets that are left need: the wheel guard, keyboard focus rings, the app style, the
images the style sheet draws with, and the overdue test the window announces from."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEvent,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QStandardPaths,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QProxyStyle,
    QStyle,
    QTimeEdit,
    QWidget,
)

from backend import clock as wall_clock
from backend.models import parse_due
from desktop.native import icons
from desktop.native.fonts import time_font
from desktop.native.look import (
    FOCUS_GAP_PX,
    FOCUS_RING_PX,
    RING_BUTTONS,
    readable_edge,
)
from desktop.native.tokens import RADIUS_CONTROL


class WheelGuard(QObject):
    """A number box, time box or dropdown takes the mouse wheel only once it has been clicked into;
    otherwise the wheel scrolls whatever it is on. Scrolling down Settings changed every box the
    pointer passed over on the way."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if not isinstance(watched, (QAbstractSpinBox, QComboBox)):
            return False
        if kind == QEvent.Type.Polish:
            # Qt gives a wheel-focus box the keyboard before the wheel arrives, so it would always
            # look clicked into by the time this filter sees the wheel.
            watched.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        elif kind == QEvent.Type.Wheel and not watched.hasFocus():
            # Ignored and stopped here, Qt offers it to the parent, which is the page's scroll area.
            event.ignore()
            return True
        return False


def steady_wheel(app: QApplication) -> None:
    if app.findChild(WheelGuard) is None:
        app.installEventFilter(WheelGuard(app))


# The focus reasons that mean the student moved with the keyboard.
KEYED = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)


class FocusRing(QWidget):
    """The keyboard focus ring of a top-bar button: FOCUS_RING_PX in the accent with FOCUS_GAP_PX of the
    page between it and the button, laid over the window just outside the button so the button keeps its
    size, its hover tint and its place. A stylesheet has no gap, and the gap here is simply not painted.
    The stylesheet gives the colour (`qproperty-colour`)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("barFocusRing")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._colour = QColor("transparent")
        self.hide()

    def _get_colour(self) -> QColor:
        return self._colour

    def _set_colour(self, value: QColor) -> None:
        self._colour = QColor(value)
        self.update()

    colour = Property(QColor, _get_colour, _set_colour)

    def around(self, button: QWidget) -> None:
        corner = button.mapTo(self.parentWidget(), QPoint(0, 0))
        reach = FOCUS_RING_PX + FOCUS_GAP_PX
        self.setGeometry(QRect(corner, button.size()).adjusted(-reach, -reach, reach, reach))
        self.raise_()
        self.show()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._colour, FOCUS_RING_PX))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half = FOCUS_RING_PX / 2
        radius = RADIUS_CONTROL + FOCUS_RING_PX + FOCUS_GAP_PX
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(half, half, -half, -half), radius, radius)


class KeyFocus(QObject):
    """Marks a button reached with the keyboard, so its focus ring shows, and clears the mark when a click
    focuses it: Qt's `:focus` also holds after a click, which would ring every button pressed. Other
    reasons, such as the window coming back to the front, leave the mark as it was."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._owner: QWidget | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if watched is self._owner:
            if kind in (QEvent.Type.FocusOut, QEvent.Type.Hide):
                self._unring()
            elif kind in (QEvent.Type.Move, QEvent.Type.Resize):
                self._ring_round(watched)
        elif kind == QEvent.Type.Resize and self._owner is not None and watched is self._owner.window():
            self._ring_round(self._owner)
        if kind == QEvent.Type.FocusIn and isinstance(watched, QAbstractButton):
            reason = event.reason()
            if reason in KEYED or reason == Qt.FocusReason.MouseFocusReason:
                keyed = reason in KEYED
                if bool(watched.property("keyfocus")) != keyed:
                    height = watched.height()
                    watched.setProperty("keyfocus", keyed)
                    watched.style().unpolish(watched)
                    watched.style().polish(watched)
                    if watched.objectName() in RING_BUTTONS:
                        watched.setMinimumHeight(max(watched.minimumHeight(), height))
            if watched.objectName() in RING_BUTTONS:
                if watched.property("keyfocus"):
                    self._ring_round(watched)
                else:
                    self._unring()
        return False

    def _ring_round(self, button: QWidget) -> None:
        window = button.window()
        ring = next((child for child in window.children() if isinstance(child, FocusRing)), None)
        if ring is None:
            ring = FocusRing(window)
        self._owner = button
        ring.around(button)

    def _unring(self) -> None:
        owner, self._owner = self._owner, None
        if owner is not None:
            for child in owner.window().children():
                if isinstance(child, FocusRing):
                    child.hide()


def keyboard_focus_rings(app: QApplication) -> None:
    if app.findChild(KeyFocus) is None:
        app.installEventFilter(KeyFocus(app))


# How far a dialog's content sits in from its edges. Qt's styles give about 11 px.
DIALOG_MARGIN = 24
LAYOUT_MARGINS = (
    QStyle.PixelMetric.PM_LayoutLeftMargin,
    QStyle.PixelMetric.PM_LayoutTopMargin,
    QStyle.PixelMetric.PM_LayoutRightMargin,
    QStyle.PixelMetric.PM_LayoutBottomMargin,
)


class AppStyle(QProxyStyle):
    """The platform's own style, with what a stylesheet cannot say: a dialog's content sits
    DIALOG_MARGIN in from its edges, and a time box writes its figures at one width, so 11:11 and
    20:00 line up. A layout given margins of its own keeps them."""

    def pixelMetric(self, metric, option=None, widget=None):  # noqa: N802
        if metric in LAYOUT_MARGINS and isinstance(widget, QDialog):
            return DIALOG_MARGIN
        return super().pixelMetric(metric, option, widget)

    def polish(self, target):  # Qt names one method for a widget, a palette and the application.
        if isinstance(target, QTimeEdit):
            target.setFont(time_font(target.font()))
        return super().polish(target)


def use_app_style(app: QApplication) -> None:
    if not isinstance(app.style(), AppStyle):
        app.setStyle(AppStyle())


_ART_STROKES = {
    "tick": ((QPoint(7, 17), QPoint(13, 23), QPoint(25, 9)), 4.0),
    "down": ((QPoint(9, 13), QPoint(16, 20), QPoint(23, 13)), 3.2),
    "up": ((QPoint(9, 19), QPoint(16, 12), QPoint(23, 19)), 3.2),
}


def _art_file(shape: str, colour: str) -> str:
    """One stroke in one colour as an image file, for a style sheet's `image:`. Drawn here rather than
    shipped, so the packaged app needs no extra file; twice its drawn size so it stays sharp."""
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
    path = folder / f"flexweek-{shape}-{QColor(colour).name()[1:]}.png"
    if not path.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        points, width = _ART_STROKES[shape]
        image = QPixmap(32, 32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(colour), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(list(points))
        painter.end()
        image.save(str(path))
    return path.as_posix()


def _switch_file(on: bool, track: str, knob: str, outline: str | None = None) -> str:
    """A switch's pill and knob as one image, the knob at the right when on. Drawn at twice the
    34 by 20 the style sheet shows it."""
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
    names = (
        QColor(track).name()[1:],
        QColor(knob).name()[1:],
        QColor(outline).name()[1:] if outline else "plain",
        "on" if on else "off",
    )
    path = folder / f"flexweek-switch-{'-'.join(names)}.png"
    if not path.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        image = QPixmap(68, 40)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(track))
        painter.drawRoundedRect(0, 0, 68, 40, 20, 20)
        if outline:
            pen = QPen(QColor(outline), 4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(2, 2, 64, 36), 18, 18)
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(knob))
        painter.drawEllipse(32 if on else 4, 4, 32, 32)
        painter.end()
        image.save(str(path))
    return path.as_posix()


def _icon_file(name: str, colour: str) -> str:
    """Lucide's `name` in `colour` as an image file, for a style sheet's `image:`, at twice 16 pixels."""
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
    path = folder / f"flexweek-icon-{name}-{QColor(colour).name()[1:]}.png"
    if not path.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        icons.pixmap(name, colour, 32).save(str(path))
    return path.as_posix()


def control_art(palette: dict) -> dict[str, str]:
    """The images the control rules in `pack_stylesheet` draw with: a tick in the accent's ink,
    chevrons for dropdowns and steppers in the muted ink, a switch on, off and greyed, and the
    chevron after More in the text colour."""
    off_outline = readable_edge(palette)
    return {
        "more": _icon_file("chevron-down", palette["text"]),
        "tick": _art_file("tick", palette["accent_ink"]),
        "down": _art_file("down", palette["muted"]),
        "up": _art_file("up", palette["muted"]),
        "switch_on": _switch_file(True, palette["accent"], palette["accent_ink"]),
        "switch_off": _switch_file(False, palette["panel"], off_outline, off_outline),
        "switch_on_off": _switch_file(True, palette["panel"], off_outline, off_outline),
        "switch_off_off": _switch_file(False, palette["panel"], off_outline, off_outline),
    }


def overdue_unfinished(items: list[dict], now: datetime | None = None) -> list[dict]:
    """Homework whose deadline is already past. The engine's unfinished list also holds work due
    today or tomorrow; this list is only what is late."""
    moment = wall_clock.now() if now is None else now
    return [item for item in items if _deadline_passed(item.get("due"), moment)]


def _deadline_passed(due: object, now: datetime) -> bool:
    if not isinstance(due, str) or not due:
        return False
    try:
        day, minute = parse_due(due)
    except ValueError:
        return False
    return datetime.combine(day, datetime.min.time()) + timedelta(minutes=minute) <= now
