"""The fields every sheet, setup page and Settings page shares (5.2 A of 0.17.2): days picked as a row of
pills, dates picked on a month drawn in the look, numbers stepped with a − and a + big enough to hit,
and clock times typed with no arrows. One module, so the block editor, Routines, alarms, work hours and
setup draw each the same way; it imports nothing of the app's own widgets, so each of those can use
it."""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import QDate, QDateTime, QEvent, QObject, QRect, QRectF, QSize, Qt, QTime, QTimer, Signal
from PySide6.QtGui import (
    QAccessible,
    QAccessibleAnnouncementEvent,
    QColor,
    QFocusEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
    QTextCharFormat,
    QValidator,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QBoxLayout,
    QButtonGroup,
    QCalendarWidget,
    QDateEdit,
    QDateTimeEdit,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from backend.slots import SLOT_MIN
from desktop.native import icons
from desktop.native.calendar import DAY_FULL, DAYS
from desktop.native.tokens import WEIGHT_STRONG
from desktop.native.weekmodel import clock_text, end_after_start_words, time_format

# A day of another month, and the letters over the days, as shares of the text colour on the card.
FAINT = 0.45
HEADER = 0.7
# Room between the month and the popup's rounded edge.
POPUP_PAD = 8
# The popup's corners, and its edge as a share of the text colour on the card.
CORNER = 10
EDGE = 0.22
# The quick lengths under a homework's time, in minutes (5.2 A of 0.17.2).
QUICK_LENGTHS = (15, 30, 45, 60, 90)
ARROWS = (("qt_calendar_prevmonth", "chevron-left"), ("qt_calendar_nextmonth", "chevron-right"))
END_OF_DAY = 24 * 60
# "15:15", "1515", "3:15 pm", "3:15pm", "315p": an hour, minutes with or without the colon, and a
# half of the day. Minutes are optional only where `whole` is not asked for.
WRITTEN_TIME = re.compile(r"(\d{1,2})(?::?(\d{2}))?\s*(?:([ap])\.?(?:m\.?)?)?")


class DayPicker(QWidget):
    """The seven days as pills on one line, each a checkable button named `name` and its index.
    `changed` says any of them was ticked or unticked."""

    changed = Signal()

    def __init__(
        self,
        days: list[int] | tuple[int, ...] = (),
        name: str = "day",
        *,
        exclusive: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("setupRow")
        self._exclusive = exclusive
        # Its height is the pills'; a form short of room squeezed the row to a sliver without this.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        line = QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        self.buttons: list[QPushButton] = []
        for index, short in enumerate(DAYS):
            button = QPushButton(short)
            button.setObjectName(f"{name}{index}")
            button.setProperty("pill", True)
            button.setCheckable(True)
            button.setChecked(index in days)
            button.setAccessibleName(DAY_FULL[index])
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoDefault(False)
            button.toggled.connect(self._toggled)
            line.addWidget(button)
            self.buttons.append(button)
        line.addStretch(1)

    def days(self) -> list[int]:
        return [index for index, button in enumerate(self.buttons) if button.isChecked()]

    def currentData(self) -> int | None:
        chosen = self.days()
        return chosen[0] if chosen else None

    def findData(self, day: int) -> int:
        return day if 0 <= int(day) < len(self.buttons) else -1

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self.buttons):
            self.set_days([index])

    def set_days(self, days: list[int]) -> None:
        for index, button in enumerate(self.buttons):
            button.setChecked(index in days)

    def set_day_labels(self, labels: list[str]) -> None:
        """What each pill says. The accessible name stays the full day."""
        for button, label in zip(self.buttons, labels, strict=True):
            button.setText(label)

    def apply_past(self, before: int | None, tip: str, allowed: set[int] | None = None) -> None:
        """Days before `before` are greyed, with `tip`. `allowed` is which other days stay on; None
        leaves every day that is not past on. A disabled pill still shows its tip."""
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        for index, button in enumerate(self.buttons):
            past = before is not None and index < before
            if past:
                button.setEnabled(False)
                button.setToolTip(tip)
            else:
                button.setEnabled(True if allowed is None else index in allowed)
                if button.toolTip() == tip:
                    button.setToolTip("")

    def _toggled(self, checked: bool) -> None:
        if self._exclusive:
            sender = self.sender()
            if checked:
                for button in self.buttons:
                    if button is not sender:
                        button.blockSignals(True)
                        button.setChecked(False)
                        button.blockSignals(False)
            elif not any(button.isChecked() for button in self.buttons):
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
                return
        self.changed.emit()


def _toward(colour: QColor, ground: QColor, share: float) -> QColor:
    """`colour` at `share` of the way from `ground`."""
    return QColor.fromRgbF(
        ground.redF() + (colour.redF() - ground.redF()) * share,
        ground.greenF() + (colour.greenF() - ground.greenF()) * share,
        ground.blueF() + (colour.blueF() - ground.blueF()) * share,
    )


class LookCalendar(QCalendarWidget):
    """A month drawn in the look: Monday first, weekends in the text colour like any other day, the
    picked day a round dot in the accent, today ringed in it, and other months' days faint. Qt's own
    drew Saturday and Sunday red and the picked day as a square (T19 of the 0.17.0 audit)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lookCalendar")
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
        for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.setWeekdayTextFormat(day, QTextCharFormat())

    def colours(self) -> tuple[QColor, QColor, QColor, QColor]:
        """The words, the card under them, the accent and the words on the accent, as the look's style
        sheet gives them to the month's grid."""
        # Looked up each time: Qt makes the month's grid again when the popup opens, and the one found
        # in __init__ was gone by then, so no day number was drawn.
        colours = self.findChild(QAbstractItemView, "qt_calendar_calendarview").palette()
        return (
            colours.color(QPalette.ColorRole.Text),
            colours.color(QPalette.ColorRole.Base),
            colours.color(QPalette.ColorRole.Highlight),
            colours.color(QPalette.ColorRole.HighlightedText),
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self._dress()

    def showEvent(self, event: object) -> None:  # noqa: N802
        self._dress()
        super().showEvent(event)

    def _dress(self) -> None:
        """What the style sheet cannot colour: the day letters, and the arrows as Lucide's chevrons."""
        text, ground, _accent, _ink = self.colours()
        letters = QTextCharFormat()
        letters.setForeground(_toward(text, ground, HEADER))
        letters.setFontWeight(WEIGHT_STRONG)
        self.setHeaderTextFormat(letters)
        for name, icon in ARROWS:
            arrow = self.findChild(QToolButton, name)
            if arrow is not None:
                arrow.setIcon(icons.icon(icon, text.name()))
        self._dress_year()

    def _dress_year(self) -> None:
        """The box that replaces the year when it is clicked, in the month button's own words and height:
        Qt's stock spin box was half as tall again as the header, with arrows that cut its digits."""
        year = self.findChild(QSpinBox, "qt_calendar_yearedit")
        month = self.findChild(QToolButton, "qt_calendar_monthbutton")
        if year is None or month is None:
            return
        year.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        year.setAlignment(Qt.AlignmentFlag.AlignCenter)
        year.setFont(month.font())
        year.setStyleSheet(
            "QSpinBox#qt_calendar_yearedit { background: transparent; border: none; padding: 4px 8px; "
            "min-height: 0; }"
        )
        year.setFixedHeight(month.sizeHint().height())

    def paintCell(self, painter: QPainter, rect: QRect, day: QDate) -> None:  # noqa: N802
        text, ground, accent, ink = self.colours()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(rect, ground)
        side = min(rect.width(), rect.height()) - 4
        dot = QRectF(0, 0, side, side)
        dot.moveCenter(QRectF(rect).center())
        usable = self.minimumDate() <= day <= self.maximumDate()
        words = text if day.month() == self.monthShown() and usable else _toward(text, ground, FAINT)
        if day == self.selectedDate():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(dot)
            words = ink
        elif day == QDate.currentDate():
            painter.setPen(QPen(accent, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(dot.adjusted(0.75, 0.75, -0.75, -0.75))
        painter.setPen(words)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(day.day()))
        painter.restore()


class PopupCard(QObject):
    """Paints a date's popup as a card in the month's own colours before the month is drawn on it."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Paint and isinstance(watched, QWidget):
            month = watched.findChild(LookCalendar)
            if month is not None:
                text, ground, _accent, _ink = month.colours()
                painter = QPainter(watched)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(QPen(_toward(text, ground, EDGE), 1))
                painter.setBrush(ground)
                painter.drawRoundedRect(QRectF(watched.rect()).adjusted(0.5, 0.5, -0.5, -0.5), CORNER, CORNER)
                painter.end()
        return False


class DateField(QDateEdit):
    """A date typed, or picked on a LookCalendar that drops under the field on the card's colour, with
    an edge and rounded corners so it reads apart from the sheet under it."""

    def __init__(self, day: QDate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The day a typed date is counted from; the window's clock where it has one.
        self.today: QDate | None = None
        self._typed = False
        self.week_steps = False
        self.editingFinished.connect(self._next_matching_date)
        self.setCalendarPopup(True)
        # The month is made on the first press or key, before Qt opens its popup: built with the
        # field, it held up the first frame of every sheet that has a date.
        self._look_calendar_ready = False
        self._popup_filters: list[QObject] = []
        if day is not None:
            self.setDate(day)

    def watch_popup(self, watcher: QObject) -> None:
        """Install `watcher` on the month's popup once that popup exists."""
        self._popup_filters.append(watcher)
        if self._look_calendar_ready:
            popup = QDateEdit.calendarWidget(self).parentWidget()
            if popup is not None:
                popup.installEventFilter(watcher)

    def calendarWidget(self) -> QCalendarWidget:  # noqa: N802
        self._ensure_look_calendar()
        return QDateEdit.calendarWidget(self)

    def _ensure_look_calendar(self) -> None:
        if self._look_calendar_ready:
            return
        self._look_calendar_ready = True
        # Made with this field as its parent, so Qt owns it, not Python's garbage collector.
        self.setCalendarWidget(LookCalendar(self))
        popup = QDateEdit.calendarWidget(self).parentWidget()
        # A rounded card with an edge, on nothing at its corners. The style sheet cannot draw it: Qt
        # left the popup's background unpainted whatever its rule said.
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.layout().setContentsMargins(POPUP_PAD, POPUP_PAD, POPUP_PAD, POPUP_PAD)
        popup.installEventFilter(PopupCard(self))
        for watcher in self._popup_filters:
            popup.installEventFilter(watcher)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt virtual
        self._ensure_look_calendar()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt virtual
        self._ensure_look_calendar()
        steps = {
            Qt.Key.Key_Up: 1,
            Qt.Key.Key_Down: -1,
            Qt.Key.Key_PageUp: -7,
            Qt.Key.Key_PageDown: 7,
        }
        if self.week_steps and event.key() in steps:
            self.setDate(self.date().addDays(steps[event.key()]))
            event.accept()
            return
        if event.text().strip() and event.text().isprintable():
            # Typing in the year gives a year; typing a day or a month leaves it to the field.
            self._typed = self.currentSection() != QDateTimeEdit.Section.YearSection
        super().keyPressEvent(event)

    def _next_matching_date(self) -> None:
        """A date typed with no year is the next one that day and month come round, not one already
        gone: a typed day or month kept the year the field had, which left it in the past."""
        typed, self._typed = self._typed, False
        today = self.today or QDate.currentDate()
        day = self.date()
        if not typed or day >= today:
            return
        while day < today:
            day = day.addYears(1)
        self.setDate(day)


def read_clock(text: str, *, end: bool = False, whole: bool = True) -> int | None:
    """The minute of the day `text` writes, or None when it writes no time. The same on either clock:
    "3:15 pm" is 15:15 on the 24-hour one too. An end of the day, 24:00 or 00:00, is 1440, and only an
    end box takes it. `whole` asks for the minutes to be written; an hour alone is "3 pm" or "15"."""
    found = WRITTEN_TIME.fullmatch(text.strip().lower())
    if found is None or (whole and found[2] is None):
        return None
    hour, minute, half = int(found[1]), int(found[2] or 0), found[3]
    if minute > 59:
        return None
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "p" else 0)
    minutes = hour * 60 + minute
    if minutes == END_OF_DAY:
        return END_OF_DAY if end else None
    if hour > 23:
        return None
    return END_OF_DAY if end and minutes == 0 else minutes


def announce(widget: QWidget, words: str, *, assertive: bool = False) -> None:
    """Have a screen reader say `words` now, without moving the keyboard (Qt 6.8's announcements)."""
    event = QAccessibleAnnouncementEvent(widget, words)
    politeness = QAccessible.AnnouncementPoliteness
    event.setPoliteness(politeness.Assertive if assertive else politeness.Polite)
    QAccessible.updateAccessibility(event)


class ProblemLine(QFrame):
    """A short problem under a field: as wide as that field, with no frame. A field that shares its
    row (Start beside End) gets the line as wide as the whole row."""

    GAP = 4
    # Used only to pick a comfortable height for the size hint. The line drawn is the field's width,
    # or the row's, never a fixed box.
    MAX_WIDTH = 360

    def __init__(self, field: QWidget) -> None:
        super().__init__(field.parentWidget() or field)
        self.field = field
        self.overlay = True
        # The row this line sits under when the field shares its row with others.
        self._row_width: Callable[[], int] | None = None
        self._row_widget: QWidget | None = None
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setProperty("problem", False)
        self.setObjectName("clockError")
        row = QGridLayout(self)
        row.setContentsMargins(0, self.GAP, 0, 0)
        row.setSpacing(6)
        row.setColumnStretch(1, 1)
        self.icon = QLabel()
        self.icon.setObjectName("clockErrorIcon")
        row.addWidget(self.icon, 0, 0, Qt.AlignmentFlag.AlignTop)
        self.text = QLabel()
        self.text.setObjectName("clockErrorText")
        self.text.setWordWrap(True)
        row.addWidget(self.text, 0, 1)
        self.action = QPushButton()
        self.action.setObjectName("clockErrorUse")
        self.action.setProperty("outlined", True)
        self.action.setAutoDefault(False)
        self.action.hide()
        row.addWidget(self.action, 0, 2, Qt.AlignmentFlag.AlignVCenter)
        self._take: Callable[[], None] | None = None
        self.action.clicked.connect(self._act)
        self.hide()
        field.installEventFilter(self)
        field.destroyed.connect(self.deleteLater)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        # A field sized after the line (one width per kind) keeps the line as wide as the field.
        if watched is self.field and event.type() == QEvent.Type.Resize and not self.overlay:
            self._match_width()
        return False

    def _match_width(self) -> None:
        """A field's line is exactly that field wide. A row's line is the layout's, as wide as the row."""
        if self._row_widget is not None:
            return
        width = self.field.width()
        if width > 0 and self.width() != width:
            self.setFixedWidth(width)

    def attach(self, layout, index: int) -> None:
        """Reserve a row under fields whose forms have a layout. A field that shares its row with
        others (Start beside End) gets the line under that whole row, so the other fields stay where
        they were and the line is as wide as the row."""
        # A caption column inside a side-by-side row is itself a vertical box. The line belongs under
        # the row, not under this one column, or it would be only as wide as End.
        shared = self._shared_row()
        if shared is not None:
            if not self._attach_under_widget(shared):
                return
            self.overlay = False
            return
        if isinstance(layout, QFormLayout):
            row, _role = layout.getWidgetPosition(self.field)
            if row < 0:
                return
            layout.insertRow(row + 1, self)
        elif isinstance(layout, QBoxLayout):
            if layout.direction() == QBoxLayout.Direction.TopToBottom and index >= 0:
                layout.insertWidget(index, self)
            elif not self._attach_under_row(layout):
                return
        elif isinstance(layout, QGridLayout):
            self._attach_in_grid(layout)
        else:
            return
        self.overlay = False

    def _attach_in_grid(self, grid: QGridLayout) -> None:
        # A row of the grid's own, as wide as the row above it, whatever the line says.
        # Read off the widgets, not the grid's items: a Python wrapper of a layout item outlives it, and
        # a new object at its address was handed back as that item.
        above = [w for w in grid.parentWidget().children() if isinstance(w, QWidget) and w is not self]
        gaps = grid.horizontalSpacing() * (len(above) - 1)
        self._row_width = lambda: gaps + sum(widget.sizeHint().width() for widget in above)
        self._row_widget = grid.parentWidget()
        grid.addWidget(self, grid.rowCount(), 0, 1, grid.columnCount())
        # A line as narrow as a pair of time boxes keeps its button under the words, not beside them.
        inside = self.layout()
        inside.removeWidget(self.action)
        inside.addWidget(self.action, 1, 1, 1, 2, Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def _form_holding(self, widget: QWidget) -> QFormLayout | None:
        """The form `widget` was added to, including one nested in the page's column."""
        host = widget.parentWidget()
        if host is None:
            return None
        layout = host.layout()
        if isinstance(layout, QFormLayout):
            return layout
        if isinstance(layout, QBoxLayout):
            for index in range(layout.count()):
                child = layout.itemAt(index).layout()
                if isinstance(child, QFormLayout) and child.indexOf(widget) >= 0:
                    return child
        return None

    def _shared_row(self) -> QWidget | None:
        """The horizontal row whose caption columns this field sits in, when there is more than one."""
        column = self.field.parentWidget()
        if column is None:
            return None
        row = column.parentWidget()
        if row is None:
            return None
        row_layout = row.layout()
        column_layout = column.layout()
        if (
            not isinstance(row_layout, QBoxLayout)
            or not isinstance(column_layout, QBoxLayout)
            or row_layout.direction() == QBoxLayout.Direction.TopToBottom
            or column_layout.direction() != QBoxLayout.Direction.TopToBottom
        ):
            return None
        columns = 0
        for at in range(row_layout.count()):
            item = row_layout.itemAt(at)
            if item is not None and item.layout() is not None:
                columns += 1
        if columns < 2:
            return None
        return row

    def _attach_under_row(self, layout: QBoxLayout) -> bool:
        row = layout.parentWidget()
        if row is None:
            return False
        return self._attach_under_widget(row)

    def _attach_under_widget(self, row: QWidget) -> bool:
        if row.parentWidget() is None:
            return False
        above = row.parentWidget().layout()
        form = above if isinstance(above, QFormLayout) else self._form_holding(row)
        if form is not None:
            at, _role = form.getWidgetPosition(row)
            if at < 0:
                return False
            form.insertRow(at + 1, self)
        elif isinstance(above, QBoxLayout) and above.direction() == QBoxLayout.Direction.TopToBottom:
            at = above.indexOf(row)
            if at < 0:
                return False
            above.insertWidget(at + 1, self)
        else:
            return False
        self._row_widget = row
        self._row_width = lambda: row.width() or row.sizeHint().width()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        return True

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._match_width()
        self._tell_host()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._tell_host()

    def _tell_host(self) -> None:
        # A line that takes room makes its sheet taller or shorter: a sheet sized when it opened would
        # scroll for the few pixels it now needs.
        refit = getattr(self.window(), "refit", None)
        if not self.overlay and callable(refit):
            refit()

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return self._row_width is not None

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        layout = self.layout()
        return layout.totalHeightForWidth(width) if layout is not None else super().heightForWidth(width)

    def sizeHint(self) -> QSize:  # noqa: N802
        # Under a row, as wide as that row asks, so a long sentence wraps instead of widening the row
        # (and a flow of rows into the next line).
        if self._row_width is None:
            return super().sizeHint()
        width = self._row_width()
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        if self._row_width is None:
            return super().minimumSizeHint()
        # Its height is for a comfortable width, not for the narrowest: a form that asks for the narrow
        # height scrolls for rows that are never that tall once laid out at the width it has.
        width = self._row_width()
        return QSize(width, self.heightForWidth(max(width, self.MAX_WIDTH)))

    def offer(self, words: str, take: Callable[[], None] | None) -> None:
        """A button beside the problem that puts it right ("Use 3:15 PM"), or none."""
        self._take = take
        self.action.setText(words)
        self.action.setVisible(bool(words) and take is not None)
        if self.isVisible() and self.overlay:
            self.place()

    def _act(self) -> None:
        if self._take is not None:
            self._take()

    def say(self, words: str) -> None:
        self.text.setText(words)
        colour = self.text.palette().color(QPalette.ColorRole.WindowText).name()
        self.icon.setPixmap(icons.pixmap("triangle-alert", colour, 16))
        self.setProperty("problem", True)
        self.style().unpolish(self)
        self.style().polish(self)
        if self.overlay:
            self.place()
        self.show()
        if self.overlay:
            self.raise_()

    def place(self) -> None:
        field = self.field
        below = field.height() + self.GAP
        holder = field.parentWidget()
        # Up to the first ancestor with room under the field, else the window.
        while holder is not None and holder.parentWidget() is not None:
            at = field.mapTo(holder, field.rect().topLeft())
            if holder.rect().contains(at.x() + self.MAX_WIDTH // 2, at.y() + below + 40):
                break
            holder = holder.parentWidget()
        holder = holder or field
        if self.parentWidget() is not holder:
            self.setParent(holder)
        at = field.mapTo(holder, field.rect().topLeft())
        # As wide as the field. A row's line is laid out with the row instead, and never drawn here.
        width = field.width()
        room = holder.width() - at.x()
        if width <= 0:
            width = max(120, min(self.MAX_WIDTH, room)) if room > 0 else 120
        elif room > 0:
            width = min(width, room)
        self.ensurePolished()
        words = self.text.palette().color(QPalette.ColorRole.WindowText).name()
        self.icon.setPixmap(icons.pixmap("triangle-alert", words, 16))
        layout = self.layout()
        self.setGeometry(at.x(), at.y() + below, width, layout.totalHeightForWidth(width))


class ClockField(QTimeEdit):
    """A clock time typed as it is written, "16:00", in the student's clock. Qt's arrows inside the box
    were too small to hit and took a quarter of it (T20 of the 0.17.0 audit); the arrow keys and the
    wheel still step it, a quarter hour at a time.

    It is a text box: the first click, Tab and Ctrl+A select the whole time, typing replaces what is
    selected, Backspace clears, and "1515", "3:15 pm" and "315p" all say 15:15. Qt's own time box edits
    one section at a time, and typed over a selection it kept the old hour. A time is taken as soon as
    the text says one. Text that says none stays in the box, outlined, with a line under it saying what
    to type; the box's time is still the last good one. An `end` box reads 00:00 as 24:00, the end of
    the day, which a QTime cannot hold."""

    # The time is settled: the student finished typing or stepped it (by hand), or a caller set it. Unlike
    # `timeChanged`, it does not fire on each key of a half-typed time.
    settled = Signal(bool)

    # Set again in __init__; Qt asks for the text while the base class is still being made.
    _end = False
    _typing = False
    _touched = False
    _settling = False
    _problem = ""
    _line: ProblemLine | None = None
    _first_click = False
    _before: int | None = None
    _start: ClockField | None = None
    _subject = ""
    _other = 0

    def __init__(
        self, time: QTime | None = None, parent: QWidget | None = None, *, end: bool = False
    ) -> None:
        super().__init__(parent)
        self._end = end
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setProperty("typed", True)
        self.setDisplayFormat(time_format())
        line = self.lineEdit()
        # Qt re-selects a section every time the cursor moves, and rewrites the text on every edit.
        line.cursorPositionChanged.disconnect()
        line.textChanged.disconnect()
        line.textEdited.connect(self._edited)
        line.installEventFilter(self)
        if time is not None:
            self.setTime(time)

    def minutes(self) -> int:
        """The minute of the day, 1440 for the end of the day in an end box."""
        return self._minutes_of(self.time())

    def problem(self) -> str:
        """The line shown under the box while its text says no time, else an empty string."""
        return self._problem

    def pair_with(self, start: ClockField, subject: str = "") -> None:
        """Make this the end box of `start`. A time typed without AM or PM is read as the one that ends
        after the start soonest, and an end at or before the start is said under this box. `subject`
        names what ends ("School") in the line that offers the other half of the day."""
        self._start = start
        self._subject = subject
        start.settled.connect(self._start_settled)

    def _read(self, text: str, *, whole: bool = True) -> int | None:
        """`text` as read_clock reads it; on the 12-hour clock an end box's bare hour takes AM or PM by
        its start: 8:30 AM to "3:15" is 3:15 PM, which a bare 3:15 on its own is not (F3)."""
        minutes = read_clock(text, end=self._end, whole=whole)
        found = WRITTEN_TIME.fullmatch(text.strip().lower())
        if minutes is None or self._start is None or found is None or found[3] or "AP" not in time_format():
            return minutes
        hour = int(found[1])
        if not 1 <= hour <= 12:
            return minutes
        morning = hour % 12 * 60 + int(found[2] or 0)
        start = self._start.minutes()
        later = [END_OF_DAY if at == 0 else at for at in (morning, morning + 12 * 60)]
        after = [at for at in later if at > start]
        return min(after) if after else minutes

    def _minutes_of(self, time: QTime) -> int:
        minutes = time.hour() * 60 + time.minute()
        return END_OF_DAY if self._end and minutes == 0 else minutes

    def _limits(self) -> tuple[int, int]:
        low, high = self._minutes_of(self.minimumTime()), self._minutes_of(self.maximumTime())
        if self._end and self.maximumTime() >= QTime(23, 59):
            high = END_OF_DAY
        return low if low != END_OF_DAY else 0, high

    def setTime(self, time: QTime) -> None:  # noqa: N802
        self._mend()
        super().setTime(time)
        if not self._typing and not self._settling:
            self.settled.emit(False)

    def _take(self, minutes: int, *, as_typed: bool = False) -> bool:
        """Make `minutes` the time; `as_typed` leaves the text as the student wrote it."""
        low, high = self._limits()
        if not low <= minutes <= high:
            return False
        self._typing = as_typed
        try:
            self.setTime(QTime(minutes // 60 % 24, minutes % 60))
        finally:
            self._typing = False
        return True

    def _edited(self, text: str) -> None:
        self._touched = True
        if self._before is None:
            self._before = self.minutes()
        minutes = self._read(text)
        if minutes is not None:
            self._take(minutes, as_typed=True)

    def _settle(self) -> None:
        """The student is done typing: an hour alone counts. Text that says no time, or one outside the
        box's limits, stays as written with a line saying what to type; the box's time goes back to the
        one from before they began (a half-typed "15:15" of "15:15x" was taken on the way), and is never
        23:59."""
        line = self.lineEdit()
        minutes = self._read(line.text(), whole=False)
        low, high = self._limits()
        before, self._before = self._before, None
        if minutes is None or not low <= minutes <= high:
            self._settling = True
            try:
                if before is not None and before != self.minutes():
                    self._take(before, as_typed=True)
            finally:
                self._settling = False
            if minutes is None:
                self._complain(f"Type a time like {clock_text(17 * 60 + 30)}.")
            else:
                self._complain(f"Type a time from {clock_text(low)} to {clock_text(high)}.")
            return
        self._settling = True
        try:
            self._take(minutes)
        finally:
            self._settling = False
        line.blockSignals(True)
        line.setText(clock_text(self.minutes()))
        line.blockSignals(False)
        self.check_after_start()
        if self._touched:
            self._touched = False
            self.settled.emit(True)

    def check_after_start(self) -> None:
        """An end at or before its start is said under the end box, where the student is, and Save and
        Next stay on it (held_on_problem); the form's own line was below the buttons."""
        if self._start is None or self._problem:
            return
        start, end = self._start.minutes(), self.minutes()
        if end > start:
            return
        other = end + 12 * 60 if end < 12 * 60 else end - 12 * 60
        self._other = other if self._subject and start < other <= END_OF_DAY else 0
        if self._other:
            self._complain(
                f"{self._subject} ends at {clock_text(end)}, before it starts at {clock_text(start)}. "
                f"Did you mean {clock_text(other)}?"
            )
            if self._line is not None:
                self._line.offer(f"Use {clock_text(other)}", self._use_other)
        else:
            self._complain(end_after_start_words(clock_text(start)))

    def _use_other(self) -> None:
        other, self._other = self._other, 0
        if other:
            self._take(other)
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            self.settled.emit(True)

    def _start_settled(self, _by_hand: bool) -> None:
        # A start moved before the end takes back the problem it caused; a new one waits until the end
        # box is left, never said while the student is still on the start.
        if self._problem and self._start is not None and self.minutes() > self._start.minutes():
            self._mend()

    def _complain(self, words: str) -> None:
        fresh = words != self._problem
        self._problem = words
        self.setAccessibleDescription(words)
        self._outline(True)
        if self._line is None:
            self._line = ProblemLine(self)
            layout = self.parentWidget().layout() if self.parentWidget() is not None else None
            if layout is not None:
                index = layout.indexOf(self)
                self._line.attach(layout, index + 1 if index >= 0 else -1)
        self._line.say(words)
        if fresh:
            announce(self, words, assertive=True)

    def clear_problem(self) -> None:
        """Take the problem line away when what the box belongs to no longer counts, such as School
        with no days ticked."""
        self._mend()

    def _mend(self) -> None:
        if not self._problem:
            return
        self._problem = ""
        self._other = 0
        self.setAccessibleDescription("")
        self._outline(False)
        if self._line is not None:
            self._line.offer("", None)
            self._line.setProperty("problem", False)
            self._line.hide()

    def _outline(self, on: bool) -> None:
        self.setProperty("invalid", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def textFromDateTime(self, dateTime: QDateTime) -> str:  # noqa: N802, N803
        # Qt asks again whenever the box is shown, reparented or restyled; a problem line under the box
        # means the text is what the student wrote, which no re-render may replace with the last good time.
        keep = self._typing or bool(self._problem)
        return self.lineEdit().text() if keep else clock_text(self._minutes_of(dateTime.time()))

    def dateTimeFromText(self, text: str) -> QDateTime:  # noqa: N802
        minutes = self._read(text, whole=False)
        if minutes is None:
            return self.dateTime()
        # In the box's own zone: Qt 6.11 keeps its value in UTC, and a local one moved it by the offset.
        return QDateTime(self.date(), QTime(minutes // 60 % 24, minutes % 60), self.dateTime().timeZone())

    def validate(self, input: str, pos: int) -> tuple[QValidator.State, str, int]:  # noqa: A002
        written = read_clock(input, end=self._end, whole=False) is not None
        return (QValidator.State.Acceptable if written else QValidator.State.Intermediate, input, pos)

    def fixup(self, input: str) -> str:  # noqa: A002
        return input if self._problem else clock_text(self.minutes())

    def stepBy(self, steps: int) -> None:  # noqa: N802
        self._settle()
        if self._problem:
            return
        now = self.minutes()
        # Up from 08:07 is 08:15 and down is 08:00: the quarter hour on each side.
        if steps < 0 and now % SLOT_MIN:
            steps += 1
        low, high = self._limits()
        self._settling = True
        try:
            self._take(max(low, min(now - now % SLOT_MIN + steps * SLOT_MIN, high)))
        finally:
            self._settling = False
        self.lineEdit().selectAll()
        self.settled.emit(True)

    def stepEnabled(self) -> QAbstractSpinBox.StepEnabledFlag:  # noqa: N802
        low, high = self._limits()
        flags = QAbstractSpinBox.StepEnabledFlag.StepNone
        if self.minutes() > low:
            flags |= QAbstractSpinBox.StepEnabledFlag.StepDownEnabled
        if self.minutes() < high:
            flags |= QAbstractSpinBox.StepEnabledFlag.StepUpEnabled
        return flags

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.matches(QKeySequence.StandardKey.SelectAll):
            # The whole time, not the one section Qt's time box would take.
            self.lineEdit().selectAll()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._settle()
        # The spin box's own handling, not the time box's, which moves between sections. Qt rewrites the
        # text from the time here; while the text says no time it must keep what was written.
        self._typing = bool(self._problem)
        try:
            QAbstractSpinBox.keyPressEvent(self, event)
        finally:
            self._typing = False

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        super().focusInEvent(event)
        reason = event.reason()
        keyed = (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )
        if reason in keyed:
            self.lineEdit().selectAll()
        # Whatever put the keyboard here without selecting the time (a click, or a sheet that focuses the
        # box when it opens), the first click selects it; the next one places the caret.
        self._first_click = reason not in keyed

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        self._first_click = False
        self._settle()
        self._typing = bool(self._problem)
        try:
            super().focusOutEvent(event)
        finally:
            self._typing = False

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002
        # One box, not one section per stop.
        return QWidget.focusNextPrevChild(self, next)

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        self._follow()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._follow()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        if self._line is not None:
            self._line.hide()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._follow()

    def _follow(self) -> None:
        if self._problem and self._line is not None and self.isVisible():
            if self._line.overlay:
                self._line.place()
            self._line.show()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.lineEdit():
            kind = event.type()
            if kind == QEvent.Type.MouseButtonDblClick:
                # A time is one thing: Qt's word selection took only the hour or the minutes.
                self.lineEdit().selectAll()
                return True
            if kind == QEvent.Type.MouseButtonPress and self._first_click:
                self._first_click = False
                # After the click is handled, or it would put the caret back. Tied to the box, so a
                # field closed before the timer fires is not called.
                line = self.lineEdit()
                QTimer.singleShot(0, line, line.selectAll)
            elif kind == QEvent.Type.KeyPress and event.matches(QKeySequence.StandardKey.SelectAll):
                self.lineEdit().selectAll()
                return True
        return super().eventFilter(watched, event)


class Stepper(QWidget):
    """A number as − value +. The box keeps its typing, its range and its steps; the two buttons step
    it and stop at its ends. `quick` adds a row of pills under it that set a length in one click, the
    one matching the value lit. Qt's arrows inside the box were too small to hit (T20)."""

    def __init__(self, box: QSpinBox, quick: tuple[int, ...] = ()) -> None:
        super().__init__()
        self.setObjectName("stepper")
        # As wide as its parts: stretched across a form, its + stood apart from where a box ends.
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.box = box
        box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setProperty("stepped", True)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        self.less = self._button("stepLess", "minus", "One step less", -1)
        self.more = self._button("stepMore", "plus", "One step more", 1)
        line.addWidget(self.less)
        line.addWidget(box)
        line.addWidget(self.more)
        line.addStretch(1)
        column.addLayout(line)
        self.chips: list[QPushButton] = []
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(False)
        if quick:
            chips = QHBoxLayout()
            chips.setContentsMargins(0, 0, 0, 0)
            chips.setSpacing(4)
            for minutes in quick:
                chip = QPushButton(str(minutes))
                chip.setObjectName("quickLength")
                chip.setProperty("pill", True)
                chip.setProperty("minutes", minutes)
                chip.setCheckable(True)
                chip.setAutoDefault(False)
                chip.setAccessibleName(f"{minutes} minutes")
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.clicked.connect(self._pick)
                chip.installEventFilter(self)
                self._chip_group.addButton(chip, len(self.chips))
                chips.addWidget(chip)
                self.chips.append(chip)
            chips.addStretch(1)
            column.addLayout(chips)
        box.installEventFilter(self)
        box.valueChanged.connect(self._follow)
        self._follow()

    def first_line(self) -> QWidget:
        """What a label beside it lines up with: the box, not the pills under it."""
        return self.box

    def _button(self, name: str, icon: str, words: str, by: int) -> QPushButton:
        button = QPushButton()
        button.setObjectName(name)
        button.setProperty("step", True)
        button.setProperty("by", by)
        button.setAccessibleName(words)
        # The box is where the keys go; its arrow keys step it as these do.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAutoDefault(False)
        button.setAutoRepeat(True)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        icons.tint(button, icon)
        button.clicked.connect(self._step)
        return button

    def _step(self) -> None:
        self.box.stepBy(int(self.sender().property("by")))

    def _pick(self) -> None:
        self.box.setValue(int(self.sender().property("minutes")))
        self._follow()

    def _follow(self, *_value: object) -> None:
        steps = self.box.stepEnabled()
        live = self.box.isEnabled()
        self.less.setEnabled(live and bool(steps & QAbstractSpinBox.StepEnabledFlag.StepDownEnabled))
        self.more.setEnabled(live and bool(steps & QAbstractSpinBox.StepEnabledFlag.StepUpEnabled))
        for chip in self.chips:
            chip.setChecked(chip.property("minutes") == self.box.value())
            chip.setEnabled(live)
        self._chip_tab_stops()

    def _chip_tab_stops(self) -> None:
        if not self.chips:
            return
        checked = next((at for at, chip in enumerate(self.chips) if chip.isChecked()), 0)
        for at, chip in enumerate(self.chips):
            chip.setFocusPolicy(
                Qt.FocusPolicy.ClickFocus
                | (Qt.FocusPolicy.TabFocus if at == checked else Qt.FocusPolicy.NoFocus)
            )
            chip.setAccessibleDescription(f"{at + 1} of {len(self.chips)}")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched in self.chips and event.type() == QEvent.Type.KeyPress:
            current = self.chips.index(watched)
            key = event.key()
            target = None
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
                target = (current - 1) % len(self.chips)
            elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
                target = (current + 1) % len(self.chips)
            elif key == Qt.Key.Key_Home:
                target = 0
            elif key == Qt.Key.Key_End:
                target = len(self.chips) - 1
            if target is not None:
                self.chips[target].click()
                self.chips[target].setFocus(Qt.FocusReason.TabFocusReason)
                return True
        if watched is self.box and event.type() == QEvent.Type.EnabledChange:
            self._follow()
        return False


def held_on_problem(*roots: QWidget) -> bool:
    """True when a shown time box in `roots` still says its text is no time, with the keyboard moved to
    the first such box. The box holds its last good time while it shows the problem, so a Save or Add
    that read it would save a time other than the one on screen."""
    for root in roots:
        boxes = [root] if isinstance(root, ClockField) else root.findChildren(ClockField)
        for box in boxes:
            if box.isVisible() and box.problem():
                box.setFocus(Qt.FocusReason.OtherFocusReason)
                box.lineEdit().selectAll()
                return True
    return False
