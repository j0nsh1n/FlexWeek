"""Screens for the 1.5.0 Material fixes: Plan's Before planning question, the Paste preview sheet, a delete
question with its red answer, the snackbar with its Undo countdown, and the reminder strip with Got it.
(Fragment of screens_sheets.py.)"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.material_support import pump
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_material_pictures import material, seed_school_and_essay

_SOURCES = (
    "desktop/native/material/qml/sheets",
    "desktop/native/material/qml/components",
    "desktop/native/material/qml/Main.qml",
    "desktop/native/material/bridge_sheets.py",
    "desktop/native/material/sheet_preview.py",
    "desktop/native/window.py",
)


def _bridge(window: NativeWindow):
    material(window)
    seed_school_and_essay(window)
    return window._material_page.bridge


def _unfinished_sheet(window: NativeWindow) -> None:
    from desktop.tests.planner.support import left_in_week_one

    qapp = QApplication.instance()
    material(window)
    left_in_week_one(qapp, window)
    window._material_page.publish()
    window._material_page.bridge.sheets.openUnfinished()
    pump(qapp, 40)


def _week_list_overdue(window: NativeWindow) -> None:
    from desktop.tests.planner.support import overdue_this_week

    qapp = QApplication.instance()
    material(window)
    overdue_this_week(qapp, window)
    window._material_page.publish()
    window._material_page.bridge.sheets.openWeekList()
    pump(qapp, 40)


def _before_planning(window: NativeWindow) -> None:
    _bridge(window).sheets.pose_question(
        NativeWindow.before_planning_question("1 overdue, 2 left from last week"), {}
    )
    pump(QApplication.instance(), 30)


def _paste_preview(window: NativeWindow) -> None:
    bridge = _bridge(window)
    bridge.week.copyBlock("school", 1)
    pump(QApplication.instance(), 10)
    bridge.week.pasteHere(5, 9 * 60)
    pump(QApplication.instance(), 30)


def _delete_homework(window: NativeWindow) -> None:
    _bridge(window).sheets.askDeleteHomework("essay")
    pump(QApplication.instance(), 30)


def _undo_snackbar(window: NativeWindow) -> None:
    bridge = _bridge(window)
    window.session.preferences = {**(window.session.preferences or {}), "motion": "normal"}
    window._apply_appearance()
    # The rig draws with Animations off; this picture is of the line, which Normal draws.
    bridge._advanced = {**bridge._advanced, "motion": "Normal"}
    bridge._publish_theme()
    window.activateWindow()
    bridge.note("Placed 1 of 1")
    pump(QApplication.instance(), 30)


def _reminder_strip(window: NativeWindow) -> None:
    _bridge(window)
    window.alert_strip.add([{"title": "Guitar practice starts soon", "body": "6:45 PM · Thu"}])
    pump(QApplication.instance(), 30)


SCREENS: list[Screen] = [
    Screen(
        id="sheets.material_before_planning_prompt",
        area="sheets",
        prepare=_before_planning,
        checks=(
            "Before planning, '1 overdue, 2 left from last week', with Plan into this week (filled), Mark as "
            "finished (tonal) and Not now (text). The card sits over a dimmed week; buttons stay inside it."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_paste_preview",
        area="sheets",
        prepare=_paste_preview,
        checks=(
            "Preview paste: 'Nothing changes until you save this preview.', one row for the pasted School "
            "with a tick, Day, Start and Minutes fields and its line about the time, Cancel and Save preview "
            "(filled). The card has an 8 px radius and nothing runs outside it."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_delete_homework_prompt",
        area="sheets",
        prepare=_delete_homework,
        checks=(
            "The Delete homework question: Cancel is a text button and Delete is the only red button, in the "
            "error colour with its own ink, readable in light and dark."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="week.material_snackbar_undo_countdown",
        area="week",
        prepare=_undo_snackbar,
        checks=(
            "The snackbar at the bottom of the week: 'Placed 1 of 1' and 'Undo 10' (seconds left, no '· s') "
            "with Ctrl+Z, and a thin line along the bottom edge of the bar, full length when it appears."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="week.material_reminder_strip",
        area="week",
        prepare=_reminder_strip,
        checks=(
            "A reminder kept on screen: a strip at the foot of the week with the reminder's words and a "
            "filled Got it button, said once (no snackbar line under it). It does not cover the day names."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_unfinished_sheet",
        area="sheets",
        prepare=_unfinished_sheet,
        checks=(
            "The Unfinished sheet: Lab report, '1 h left, due <day>, Left from last week', with Start focus "
            "(text), Find a time (tonal) and Delete (text) on its row. Nothing runs outside the card."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
    Screen(
        id="sheets.material_week_list_overdue",
        area="sheets",
        prepare=_week_list_overdue,
        checks=(
            "Week as a list: the Wednesday row for Bio reading reads its times, 'Overdue, was due Fri <day>' "
            "and 'Pinned'; no other row carries either word."
        ),
        sources=_SOURCES,
        styles=("material",),
    ),
]
