"""What the Widgets that are left need: the wheel guard, the app style, and the overdue test the
window announces from."""

from __future__ import annotations

from datetime import datetime, timedelta

from flexweek_engine import parse_due  # type: ignore[import-untyped]
from PySide6.QtCore import (
    QEvent,
    QObject,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QProxyStyle,
    QStyle,
    QTimeEdit,
)

from backend import clock as wall_clock
from desktop.native.fonts import time_font


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
