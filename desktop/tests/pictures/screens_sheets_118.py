"""Screens for #118: a fixed time that repeats every week (the block sheet's switch and Until, the save
question, the notice with Undo, the doubled-weeks prompt) and reminders kept on screen as cards."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtWidgets import QApplication

from desktop.native.calendar import date_for_day
from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_material_pictures import material, seed_school_and_essay
from desktop.tests.window_support import settled

MATERIAL = ("material",)
FRIDAY = 4
SHEET_SOURCES = (
    "desktop/native/material/qml/sheets",
    "desktop/native/material/qml/components",
    "desktop/native/material/bridge_sheets.py",
    "desktop/native/material/sheet_block.py",
)
CARD_SOURCES = (
    "desktop/native/material/qml/components/ReminderCard.qml",
    "desktop/native/material/qml/Main.qml",
    "desktop/native/kept_alerts.py",
)


def _sheets(window: NativeWindow):
    material(window)
    seed_school_and_essay(window)
    return window._material_page.bridge.sheets


def _friday(window: NativeWindow, weeks: int = 0) -> str:
    base = date.fromisoformat(date_for_day(window.session.week_start, FRIDAY))
    return (base + timedelta(days=7 * weeks)).isoformat()


def _fill_guitar(sheets) -> None:
    sheets.openBlock()
    sheets.setText("title", "Guitar")
    sheets.next()
    for day in [item["value"] for item in sheets.form["days"] if item["on"]]:
        sheets.toggleDay(day)
    sheets.toggleDay(FRIDAY)
    sheets.setText("start", "17:00")
    sheets.setFlag("repeat", True)


def _settle(window: NativeWindow) -> None:
    qapp = QApplication.instance()
    settled(qapp, window)
    pump(qapp, 30)


def _switch_on_until(window: NativeWindow) -> None:
    sheets = _sheets(window)
    _fill_guitar(sheets)
    sheets.setText("until", _friday(window, 3))
    pump(QApplication.instance(), 30)


def _until_problem(window: NativeWindow) -> None:
    sheets = _sheets(window)
    _fill_guitar(sheets)
    early = (date.fromisoformat(_friday(window)) - timedelta(days=1)).isoformat()
    sheets.setText("until", early)
    pump(QApplication.instance(), 30)


def _weekly_guitar(window: NativeWindow):
    """Guitar repeating every Friday at 5 PM, saved, with the sheet closed."""
    sheets = _sheets(window)
    _fill_guitar(sheets)
    sheets.next()
    sheets.next()
    _settle(window)
    sheets.dismissNotice()
    repeat = next(r for r in window.session.repeats if r["title"] == "Guitar")
    return sheets, repeat


def _save_question(window: NativeWindow) -> None:
    sheets, repeat = _weekly_guitar(window)
    sheets.editBlock(repeat["id"], -1)
    sheets.setText("start", "18:00")
    sheets.next()
    pump(QApplication.instance(), 30)


def _notice_with_undo(window: NativeWindow) -> None:
    sheets, repeat = _weekly_guitar(window)
    sheets.editBlock(repeat["id"], -1)
    sheets.setText("start", "18:00")
    sheets.next()
    sheets.answer("later")
    _settle(window)


def _doubled_weeks(window: NativeWindow) -> None:
    sheets = _sheets(window)
    session = window.session
    first = session.week_start
    session.load_week((date.fromisoformat(first) + timedelta(days=7)).isoformat())
    _settle(window)
    session.add_block({"id": "hand", "title": "Guitar", "kind": "locked", "category": "extra",
                       "start": "17:00", "duration_min": 60, "days": [FRIDAY]})  # fmt: skip
    session.save()
    _settle(window)
    session.load_week(first)
    _settle(window)
    _fill_guitar(sheets)
    sheets.next()
    sheets.next()
    _settle(window)


def _two_reminder_cards(window: NativeWindow) -> None:
    from desktop.tests.settings.support_reminders import add_practice, at, choose, tick, with_stand_ins

    qapp = QApplication.instance()
    material(window)
    with_stand_ins(window)
    window._tray_icon = None  # no pop-ups on this computer, so reminders stay as cards
    at(18, 30)
    choose(qapp, window, reminder_lead_min=10)
    add_practice(qapp, window)
    tick(qapp, window, 35)
    window.session.add_block({"id": "chess", "title": "Chess", "kind": "locked", "category": "class",
                              "start": "18:50", "duration_min": 30, "days": [3]})  # fmt: skip
    window.session.save()
    settled(qapp, window)
    tick(qapp, window, 40)
    pump(qapp, 30)


SCREENS: list[Screen] = [
    Screen(
        id="sheets.material_weekly_switch_on_until",
        area="sheets",
        prepare=_switch_on_until,
        checks=(
            "Add fixed time, When step, for Guitar on Friday at 5 PM with 'Repeats every week' on and Until "
            "set three weeks ahead. The switch row's label lines up with 'Days' and the fields' left edge, "
            "the switch with the End field's right edge; the row is no taller than the switch. Under it, "
            "'Until' with the date button and 'No end'. Spacing above and below the rows matches the "
            "sheet's other rows. Next is the only filled button."
        ),
        sources=SHEET_SOURCES,
        styles=MATERIAL,
    ),
    Screen(
        id="sheets.material_weekly_until_problem",
        area="sheets",
        prepare=_until_problem,
        checks=(
            "The same sheet with Until set before the first day: the error line under the Until row "
            "('Until can't be before the first day, ...') in the sheet's error style, lined up with the "
            "rows above."
        ),
        sources=SHEET_SOURCES,
        styles=MATERIAL,
    ),
    Screen(
        id="sheets.material_weekly_save_question",
        area="sheets",
        prepare=_save_question,
        checks=(
            "'Change Guitar?' after changing a weekly Guitar's start: two picked cards, 'This week only' "
            "and 'This week and every week after', drawn like the delete question's cards, over a dimmed "
            "Edit fixed time sheet. Save is the only filled button."
        ),
        sources=SHEET_SOURCES,
        styles=MATERIAL,
    ),
    Screen(
        id="sheets.material_weekly_notice_with_undo",
        area="sheets",
        prepare=_notice_with_undo,
        checks=(
            "The week after 'This week and every week after': the notice 'Changed Guitar from this week on. "
            "Undo also takes back anything changed after it.' with its Undo, readable on its bar."
        ),
        sources=SHEET_SOURCES,
        styles=MATERIAL,
    ),
    Screen(
        id="sheets.material_weekly_doubled_prompt",
        area="sheets",
        prepare=_doubled_weeks,
        checks=(
            "'Guitar is already in a later week' (one week named) with OK, over a dimmed week. The "
            "notice bar, if shown, is behind the dimming, not in front of it."
        ),
        sources=SHEET_SOURCES,
        styles=MATERIAL,
    ),
    Screen(
        id="settings.material_reminder_cards",
        area="settings",
        prepare=_two_reminder_cards,
        checks=(
            "Two reminders kept on screen (no pop-ups on this computer), newest on top: 'Chess starts soon' "
            "over 'Guitar practice starts soon', each with Snooze and Close. They sit in the bottom right "
            "corner, 16 px from the window's right and bottom edges, and do not cover Thursday's 6:45 PM "
            "and 6:50 PM blocks. Each card stands apart from what is behind it (a visible edge); Snooze "
            "and Close are both readable and Close is the filled one."
        ),
        sources=CARD_SOURCES,
        styles=MATERIAL,
    ),
]
