"""Pictures of the homework sheets' parts (R3 forms lane, chunk H7): which dialog button is filled, the date
picker's month, the overdue card. These replace the pixel checks of test_one_filled_button, test_date_picker,
test_date_typing and test_overdue_card_fit."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QToolButton, QVBoxLayout, QWidget

from desktop.native.fields import DateField
from desktop.native.motion import settle
from desktop.native.setup import FIRST
from desktop.native.widgets import UnfinishedPanel
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_buttons import RESTORE_POINT, makers
from desktop.tests.sheets.support_date_picker import opened, picked_near_today
from desktop.tests.sheets.support_overdue_card import DESIGNS, LONG_WORDS, show_overdue_card
from desktop.tests.waiting import wait_until


def _pump() -> None:
    for _ in range(6):
        QApplication.processEvents()


def _still(root: QWidget) -> None:
    """End the fade a dialog's content makes as it opens, so the picture is of the screen as it stays."""
    for widget in (root, *root.findChildren(QWidget)):
        settle(widget)


DIALOG_SOURCES = (
    "desktop/native/widgets.py",
    "desktop/native/settings.py",
    "desktop/native/devices.py",
    "desktop/native/look_editor.py",
    "desktop/native/look.py",
)


def _dialog_screen(kind: type, index: int, make: Callable[[QWidget], QDialog]) -> Screen:
    def prepare(window: QWidget) -> QWidget:
        dialog = make(window)
        dialog.show()
        _pump()
        _still(dialog)
        return dialog

    return Screen(
        id=f"sheets.dialog_buttons_{kind.__name__.lower()}_{index}",
        area="sheets",
        prepare=prepare,
        checks=(
            f"{kind.__name__}: at most one button is drawn filled in the accent colour (a button counts "
            "as filled when more than half of its pixels are the accent). The answer is the filled one; "
            "the others are outlined or plain. Ticked day pills and setup chips are choices shown, not "
            "buttons."
        ),
        sources=DIALOG_SOURCES,
    )


def _restore(window: QWidget) -> QWidget:
    from desktop.native import settings

    dialog = settings.RestoreDialog(window, [RESTORE_POINT], None, None)
    dialog.show()
    _pump()
    _still(dialog)
    return dialog


def _unfinished(window: QWidget) -> QWidget:
    panel = UnfinishedPanel(window)
    panel.show()
    _pump()
    _still(panel)
    return panel


def _month(window: QWidget) -> QWidget:
    _dialog, popup, _month = opened(QApplication.instance(), window, picked_near_today())
    return popup


def _setup_month(window: QWidget) -> QWidget:
    """The month of the first homework's due date in setup, opened by a click on its arrow."""
    window._open_setup(FIRST, first_run=True)
    setup = window.setup_page
    # Setup draws its style pictures in windows of their own, one at a time; each one shown closes any
    # calendar that is open.
    wait_until(
        None,
        lambda: not setup._pending_pictures and not setup._warm.isActive(),
        what="setup's style pictures drawn",
    )
    setup._show(FIRST)
    _pump()
    field = setup.homework_rows[0].due.date
    QTest.mouseClick(
        field,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(field.width() - 6, field.height() // 2),
    )
    popup = field.findChild(QWidget, "qt_datetimedit_calendar")
    wait_until(None, lambda: popup is not None and popup.isVisible(), what="the month opening")
    _pump()
    return popup


def _year_box(window: QWidget) -> QWidget:
    host = QWidget(window)
    field = DateField(QDate(2026, 10, 3))
    QVBoxLayout(host).addWidget(field)
    host.resize(500, 400)
    host.show()
    _pump()
    QTest.mouseClick(
        field,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(field.width() - 6, field.height() // 2),
    )
    _pump()
    month = field.calendarWidget()
    month.findChild(QToolButton, "qt_calendar_yearbutton").click()
    _pump()
    return month.window()


def _overdue(main: str, long_words: bool) -> Callable[[QWidget], QWidget]:
    def prepare(window: QWidget) -> QWidget:
        show_overdue_card(window, main)
        if long_words:
            window.left_chip_text.setText(LONG_WORDS)
            window._fit_left_chip()
        for _ in range(20):
            QApplication.processEvents()
        return window.left_chip

    return prepare


OVERDUE_SOURCES = ("desktop/native/window.py", "desktop/native/layouts")
OVERDUE_WHOLE = (
    "At 1024 x 640 with Large text and the long words '1 overdue · 3 left from last week', the Plan and "
    "Done buttons each show their whole label (neither is squeezed below its natural width, neither is "
    "cut off) and both sit inside the overdue card."
)

SCREENS: list[Screen] = [
    *(
        _dialog_screen(kind, index, make)
        for kind, ways in makers().items()
        for index, make in enumerate(ways)
    ),
    Screen(
        id="sheets.restore_dialog_outlined_actions",
        area="sheets",
        prepare=_restore,
        checks=(
            "Hide preview and Save restore point are outlined: a 1 px edge in the outline colour runs "
            "along the top of each button and its centre is not the outline colour. Close (the sheet's x) "
            "stays plain. Restore is the only button filled in the accent."
        ),
        sources=("desktop/native/settings.py", "desktop/native/look.py"),
    ),
    Screen(
        id="sheets.unfinished_panel_dismiss_outlined",
        area="sheets",
        prepare=_unfinished,
        checks=(
            "The Unfinished panel's dismiss button is outlined: a 1 px edge in the outline colour along "
            "its top, and its centre is not the outline colour."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
    ),
    Screen(
        id="sheets.date_picker_month",
        area="sheets",
        prepare=_month,
        checks=(
            "Weekdays and weekends are in the same text colour (Saturday and Sunday are not red), and the "
            "S and S of the header are coloured as M to F. The picked day is a round disc filled in the "
            "accent (not a square), today is a ring in the accent (not filled). The month drops on a "
            "rounded card: nothing in its corners, a visible edge, the card colour inside it. The whole "
            "month's grid fits its view: the last column (Sunday) and the last week are not cut off, "
            "and the popup lies inside the screen (at Normal and at Large text)."
        ),
        sources=("desktop/native/fields.py", "desktop/native/look.py"),
        main=True,
    ),
    Screen(
        id="sheets.date_picker_month_in_setup",
        area="sheets",
        prepare=_setup_month,
        checks=(
            "The month opened from setup's first homework due date shows its whole grid: the last "
            "column (Sunday) and the last week are not cut off, and the popup lies inside the screen "
            "(at Normal and at Large text)."
        ),
        sources=("desktop/native/fields.py", "desktop/native/setup.py", "desktop/native/look.py"),
        main=True,
    ),
    Screen(
        id="sheets.date_picker_year_box",
        area="sheets",
        prepare=_year_box,
        checks=(
            "The year box in the picker's header is as tall as the month button beside it, in the same "
            "font weight, with no arrows over its digits, and the four digits of the year are not cut off."
        ),
        sources=("desktop/native/fields.py", "desktop/native/look.py"),
    ),
    *(
        Screen(
            id=f"sheets.overdue_card_{design}",
            area="sheets",
            prepare=_overdue(design, True),
            checks=OVERDUE_WHOLE
            + (
                " The card is narrow here, so the buttons are on a row under the words, lined up under them."
                if design == "classic"
                else ""
            ),
            sources=OVERDUE_SOURCES,
            main=True,
        )
        for design in DESIGNS
    ),
    Screen(
        id="sheets.overdue_card_short_words",
        area="sheets",
        prepare=_overdue("classic", False),
        checks=(
            "With room for the words and both buttons whole, nothing moves: both buttons share the "
            "words' line and the row under the words is not showing."
        ),
        sources=OVERDUE_SOURCES,
        main=True,
    ),
]
