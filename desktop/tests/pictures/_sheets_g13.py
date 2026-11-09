"""Pictures of the Widgets sheets and dialogs: what the old sheet and dialog tests asserted about
colours, pixels, sizes and positions. A few screens belong to other areas (Settings, Setup, the
recovery page): their ids say so. The lead gathers this fragment into screens_sheets.py (and the
others into theirs)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QPushButton,
    QScrollArea,
    QWidget,
)

from desktop.native.look_editor import leave_sheet
from desktop.native.settings import AboutDialog, AccountDialog, HelpDialog
from desktop.native.setup import WEEK as SETUP_WEEK
from desktop.native.setup import SetupPage
from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import (
    BlockDialog,
    ChooseTimeDialog,
    ConfirmSheet,
    HomeworkDialog,
    LateDialog,
    PlanReview,
    PreviewDialog,
    RoutineDialog,
    SchoolHoursDialog,
    SpreadDialog,
    UnfinishedPanel,
    confirm_sheet,
)
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_dialogs import ESSAY, WEEK, choose_time, school, shown, soccer
from desktop.tests.test_homework_form import essay, go_when
from desktop.tests.test_regress_item0_time_boxes import state

SOURCES = ("desktop/native/widgets.py", "desktop/native/look.py", "desktop/native/tokens.py")
SETTLE_TURNS = 6


def _app() -> QApplication:
    return QApplication.instance()


def _settle() -> None:
    for _ in range(SETTLE_TURNS):
        _app().processEvents()


def _open(
    make: Callable[[NativeWindow], QDialog], width: int | None = None
) -> Callable[[NativeWindow], QDialog]:
    """A prepare that opens the sheet `make` builds over the window (resized to `width` wide first)."""

    def prepare(window: NativeWindow) -> QDialog:
        if width is not None:
            window.resize(width, 800)
            _settle()
        return shown(_app(), make(window))

    return prepare


# What every sheet shares; the screens that add to it say so in their own checks.
_FRAME = (
    "A frameless card over the week, which is dimmed to 40 % black behind it (the dim is the same black in "
    "every design, and a still of the week sits under it). The card is centred on the window across, "
    "wholly inside the window, and has a title and a close button in its top right corner. "
)
_WIDTH = (
    "Its card is {width} px wide at Normal text ({kind}); at Large text the width grows with the text "
    "(13 pt to 15 pt) and nothing is cut to fit. "
)
_FORM, _LIST = "a form's width", "a list's width"

# Add homework ---------------------------------------------------------------------------------------------


def _add_homework(window: NativeWindow) -> QDialog:
    return shown(_app(), HomeworkDialog(window, today=WEEK))


def _add_homework_when(window: NativeWindow) -> QDialog:
    dialog = shown(_app(), HomeworkDialog(window, today=WEEK))
    go_when(dialog)
    dialog.findChild(QCheckBox, "homeworkDueTimed").setChecked(True)
    _settle()
    return dialog


def _edit_homework_details(window: NativeWindow) -> QDialog:
    dialog = shown(_app(), HomeworkDialog(window, essay(), WEEK))
    dialog.findChild(QCheckBox, "homeworkDueTimed").setChecked(True)
    dialog.more_details.setChecked(True)
    _settle()
    return dialog


# Fixed times ----------------------------------------------------------------------------------------------


def _edit_fixed_time(window: NativeWindow) -> QDialog:
    return shown(_app(), BlockDialog(window, soccer(), occurrence_day=3))


def _add_fixed_time(window: NativeWindow) -> QDialog:
    dialog = shown(_app(), BlockDialog(window, day=3, start="17:00"))
    dialog.title.setFocus()
    _settle()
    return dialog


def _fixed_time_in_a_short_window(window: NativeWindow) -> QDialog:
    window.resize(1280, 520)
    _settle()
    return shown(_app(), BlockDialog(window, soccer(), occurrence_day=3))


def _fixed_time_bad_start(window: NativeWindow) -> QDialog:
    set_clock_24h(False)
    dialog = shown(_app(), BlockDialog(window, school(), occurrence_day=1))
    start = dialog.start
    start.lineEdit().setText("abc")
    start._edited("abc")
    start._settle()
    _settle()
    return dialog


# Other sheets ---------------------------------------------------------------------------------------------


def _late_after_preview(window: NativeWindow) -> QDialog:
    late = shown(_app(), LateDialog(window, "School"))
    late.show_trace({"moves": [], "unplaced": []}, {})
    _settle()
    return late


def _choose_time_clash(window: NativeWindow) -> QDialog:
    waiting = {"id": "w", "title": "Essay", "duration_min": 60, "days": [1, 2]}
    return shown(_app(), ChooseTimeDialog(window, waiting, WEEK, [1, 2], [soccer()], None, 1))


def _leave_look_editor(window: NativeWindow) -> QDialog:
    return shown(_app(), leave_sheet(window, "Evening", True))


def _confirm(danger: bool) -> Callable[[NativeWindow], QDialog]:
    return _open(
        lambda window: confirm_sheet(window, "Delete event", "Delete Soccer?", "Delete", danger=danger)
    )


def _manage_account(window: NativeWindow) -> QDialog:
    return shown(_app(), AccountDialog(window, 8, {"username": "maya_r"}))


def _manage_account_bottom(window: NativeWindow) -> QDialog:
    account = _manage_account(window)
    bar = account.findChild(QScrollArea, "accountScroll").verticalScrollBar()
    bar.setValue(bar.maximum())
    _settle()
    return account


def _preview_save_off(window: NativeWindow) -> QDialog:
    row = {
        "block": {
            "id": "b0",
            "title": "History essay",
            "kind": "flexible",
            "days": [0],
            "start": "16:00",
            "duration_min": 60,
            "category": "assignments",
        },
        "day": 0,
        "fixed": False,
        "checked": False,
    }
    return shown(_app(), PreviewDialog(window, "Paste", "", [row], []))


def _disabled_primary(window: NativeWindow) -> QDialog:
    """The style sheet's rule for a visible main button that is off, on a plain dialog."""
    dialog = QDialog(window)
    button = QPushButton("Continue", dialog)
    button.setFixedSize(160, 40)
    button.setEnabled(False)
    button.move(24, 24)
    dialog.resize(208, 88)
    return shown(_app(), dialog)


_ANSWERS = {
    "two": (
        ("skip", "Skip without School", "outlined"),
        ("keep", "Keep School and go on", ""),
    ),
    "three": (
        ("stay", "Cancel", "outlined"),
        ("week", "This week only", ""),
        ("every", "This week and later", "danger"),
    ),
    "four": (
        ("stay", "Cancel", "outlined"),
        ("day", "This day only", ""),
        ("week", "This week only", ""),
        ("every", "This week and later", "danger"),
    ),
}


def _answers(which: str, width: int) -> Callable[[NativeWindow], QDialog]:
    answers = _ANSWERS[which]
    return _open(
        lambda window: ConfirmSheet(window, "Question?", "Which one?", answers, default=answers[0][0]),
        width,
    )


# The Unfinished panel -------------------------------------------------------------------------------------


def _unfinished_items(count: int) -> list[dict]:
    return [
        {"id": f"a{n}", "title": f"History essay {n}", "remaining_min": 60, "due": "2000-01-15T12:00"}
        for n in range(count)
    ]


def _unfinished(count: int) -> Callable[[NativeWindow], QWidget]:
    def prepare(window: NativeWindow) -> QWidget:
        holder = QWidget(window)
        holder.setGeometry(window.rect())
        holder.show()
        holder.raise_()
        panel = UnfinishedPanel(holder)
        panel.move(20, 20)
        panel.resize(900, 600)
        panel.set_items(_unfinished_items(count))
        _settle()
        return holder

    return prepare


def _unfinished_styled_late(window: NativeWindow) -> QWidget:
    """Filled first and dressed after, as when a look is chosen while the panel is open."""
    holder = QWidget()
    holder.resize(940, 640)
    holder.show()
    panel = UnfinishedPanel(holder)
    panel.resize(900, 600)
    panel.set_items(_unfinished_items(1))
    _settle()
    holder.setStyleSheet(window.styleSheet())
    _settle()
    window._picture_holder = holder
    return holder


def _plan_review(window: NativeWindow) -> QWidget:
    panel = PlanReview(window)
    panel.set_trace(
        {
            "placed": [{"id": "essay"}],
            "unplaced": [{"id": "poster", "title": "Poster"}],
            "moves": [],
            "explanations": [],
        },
        {"essay": "Essay", "poster": "Poster"},
        WEEK,
        (2, 1),
    )
    panel.resize(panel.sizeHint().expandedTo(panel.minimumSizeHint()))
    panel.move(40, 100)
    panel.show()
    panel.raise_()
    _settle()
    return panel


# Pages of other areas -------------------------------------------------------------------------------------


def _recovery_continue_off(window: NativeWindow) -> None:
    window._show_recovery(["aaaa-bbbb", "cccc-dddd"])
    _settle()
    return None


def _settings_labels(window: NativeWindow) -> None:
    window.resize(1280, 800)
    window._open_settings()
    _settle()
    window._settings.nav.setCurrentRow(2)
    _settle()
    return None


def _setup_page(window: NativeWindow) -> SetupPage:
    set_clock_24h(False)
    setup = SetupPage(window)
    setup.motion = "off"
    setup.setGeometry(window.rect())
    setup.open(state())
    setup._show(SETUP_WEEK)
    setup.show()
    setup.raise_()
    _settle()
    return setup


def _bad_end(times: object) -> None:
    times.start.setTime(QTime(8, 30))
    end = times.end
    end.lineEdit().setText("3:15a")
    end._edited("3:15a")
    end._settle()
    _settle()


def _setup_bad_school_end(window: NativeWindow) -> SetupPage:
    setup = _setup_page(window)
    _bad_end(setup.school_times)
    return setup


def _setup_bad_activity_end(window: NativeWindow) -> SetupPage:
    setup = _setup_page(window)
    row = setup.activities[0]
    row.name.setText("Soccer")
    row.days.set_days([1])
    _settle()
    _bad_end(row.times)
    return setup


def _setup_bad_school_end_with_an_activity(window: NativeWindow) -> SetupPage:
    setup = _setup_page(window)
    setup.activities[0].name.setText("Soccer")
    _settle()
    _bad_end(setup.school_times)
    return setup


SCREENS: list[Screen] = [
    # --- Add homework -------------------------------------------------------------------------------------
    Screen(
        id="sheets.add_homework",
        area="sheets",
        prepare=_add_homework,
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "It opens on What (three questions in all) with the keyboard in the title; the primary reads Next. "
        "The scrolled body is the same paper as the card, with no pale box inset inside it, in light and "
        "dark. Save and Cancel sit outside the scrolled body, under a 1 px divider as wide as the body "
        "above it. The sheet is wide enough to read (at least 440 px) and at least 400 px tall.",
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="sheets.add_homework_when",
        area="sheets",
        prepare=_add_homework_when,
        checks=(
            "Add homework on its When step with At a set time ticked. The sheet is as tall as its content "
            "up to 90 % of the window (card height at most 0.9 of the window's), and Due by and its time "
            "box fit with no inner scroll bar. Both fields sit fully inside the scrolled body. The Due "
            "label sits above its date box, and both start at the same left edge as the title."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.edit_homework_details_open",
        area="sheets",
        prepare=_edit_homework_details,
        checks=(
            "Edit homework with More details open and a set due time: the sheet is the tall one, "
            "within 2 px of 90 % of a 800 px window's height, and its body scrolls (a scroll bar shows)."
        ),
        sources=SOURCES,
    ),
    # --- Fixed times --------------------------------------------------------------------------------------
    Screen(
        id="sheets.edit_fixed_time",
        area="sheets",
        prepare=_edit_fixed_time,
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "Edit fixed time for Soccer practice (Tue and Thu), opened on Thursday. The keyboard is in the "
        "title and the filled Save is the primary. Each label (Title, Days, Apply to, Start, End, "
        "Category) sits above its field and starts at the same left edge; every field starts at the one "
        "edge of the card except End, which sits beside Start. Start and End are the same width and "
        "narrower than half the title box; the Category dropdown is narrower than the title box. The "
        "This day only / Every Tue and Thu choice sits under the days, below the title.",
        sources=SOURCES,
        main=True,
    ),
    Screen(
        id="sheets.add_fixed_time",
        area="sheets",
        prepare=_add_fixed_time,
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "Add fixed time on its first step with the keyboard in the title. The focused text box's ring is "
        "the 1 px accent border (a 2 px border made Add homework and Routines scroll), in the accent "
        "rather than the hairline colour.",
        sources=SOURCES,
    ),
    Screen(
        id="sheets.fixed_time_in_a_short_window",
        area="sheets",
        prepare=_fixed_time_in_a_short_window,
        checks=(
            "Edit fixed time in a 1280 x 520 window: the sheet scrolls, and the day pills are not "
            "squeezed to a sliver (each is at least its size hint tall)."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.fixed_time_bad_start",
        area="sheets",
        prepare=_fixed_time_bad_start,
        checks=(
            "Edit fixed time (School) after typing letters in Start: the problem line takes its own row "
            "between Start and the duration line. Start and End stay exactly where they were. The line "
            "does not overlap End, the duration line, Category or any other widget, and stays inside "
            "the sheet's right edge."
        ),
        sources=SOURCES + ("desktop/native/fields.py",),
    ),
    # --- The other sheets over the week ---------------------------------------------------------------------
    Screen(
        id="sheets.routines",
        area="sheets",
        prepare=_open(lambda window: RoutineDialog(window, {}, [soccer()], WEEK)),
        checks=_FRAME
        + _WIDTH.format(width=600, kind=_LIST)
        + "Routines with nothing saved: everything shows at once, with no scroll bar, and Apply is not "
        "below the sheet. The fixed time in the list is ticked with the app's own accent-filled check "
        "box (many accent pixels in the box), not Qt's own mark beside it. Its top edge is at the same "
        "height as Help's and About's, and the card has at least 16 px of padding at its bottom.",
        sources=SOURCES,
    ),
    Screen(
        id="sheets.help",
        area="sheets",
        prepare=_open(lambda window: HelpDialog(window)),
        checks=_FRAME
        + _WIDTH.format(width=600, kind=_LIST)
        + "Help: its top edge is at the same height as Routines' and About's, and its last row is not on "
        "the card's edge (at least 16 px of padding at the bottom).",
        sources=SOURCES + ("desktop/native/settings.py",),
    ),
    Screen(
        id="sheets.about",
        area="sheets",
        prepare=_open(lambda window: AboutDialog(window, {"mode": "local"}, "/nowhere")),
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "About: its top edge is at the same height as Help's and Routines'.",
        sources=SOURCES + ("desktop/native/settings.py",),
    ),
    Screen(
        id="sheets.school_hours",
        area="sheets",
        prepare=_open(lambda window: SchoolHoursDialog(window, None)),
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "School hours: Start and End are labelled above their boxes, with no 'from' word between them.",
        sources=SOURCES,
    ),
    Screen(
        id="sheets.choose_a_time",
        area="sheets",
        prepare=_open(choose_time),
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "Choose a time: the Day, Start and Length labels each sit above their field, and the labels "
        "and fields start at the same left edge as the title.",
        sources=SOURCES,
    ),
    Screen(
        id="sheets.choose_a_time_clash",
        area="sheets",
        prepare=_choose_time_clash,
        checks=(
            "Choose a time on a day that already has Soccer practice at that time: the line saying so "
            "is the amber row with a warning mark drawn like the app's other icons, in light and dark. "
            "The row is the conflict fill (checked at its right end) with its words in the conflict "
            "text colour, which reads at least 7 to 1 on that fill."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.spread",
        area="sheets",
        prepare=_open(lambda window: SpreadDialog(window, ESSAY, WEEK)),
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "Spread homework: the Sessions of and Starting labels each sit above their field, at the same "
        "left edge as the title.",
        sources=SOURCES,
    ),
    Screen(
        id="sheets.running_late_before_preview",
        area="sheets",
        prepare=_open(lambda window: LateDialog(window, "Starting from 15:40 today (Thursday).")),
        checks=_FRAME
        + _WIDTH.format(width=440, kind=_FORM)
        + "Running late before a preview: Preview is the one filled button, Cancel is bare. Accept late "
        "start is not shown. The summary line has no empty row yet. Where the greyed Accept shows (as "
        "the Why-off line says to preview first) it is a pale tint with its words in the text colour, "
        "at least 7 to 1 on it, and at least as wide as its words plus 20 px each side, at least 36 px "
        "tall (40 at Large text) with 8 px above and below the words.",
        sources=SOURCES,
    ),
    Screen(
        id="sheets.running_late_after_preview",
        area="sheets",
        prepare=_late_after_preview,
        checks=(
            "Running late after a preview: Accept late start replaces Preview on the same row and is the "
            "one filled button, Cancel stays bare, and the summary line now shows."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.leave_look_editor_question",
        area="sheets",
        prepare=_leave_look_editor,
        checks=(
            "The question on leaving the look editor with changes unsaved: Save is the one filled "
            "answer, Discard changes is outlined with an edge in the error colour, and Cancel and Keep "
            "without saving are quiet. All four answers are as wide as their words, none squeezed, at "
            "Normal and Large text."
        ),
        sources=SOURCES + ("desktop/native/look_editor.py",),
    ),
    Screen(
        id="sheets.confirm_destroying",
        area="sheets",
        prepare=_confirm(True),
        checks=(
            "A confirmation that destroys something: Cancel is outlined and the default; the Delete answer "
            "is filled in the error colour (red at the top edge of its button)."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.confirm_keeping",
        area="sheets",
        prepare=_confirm(False),
        checks=(
            "A confirmation that destroys nothing (like Sign out): the answer next to Cancel is not red; "
            "it is the app's normal filled button."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.confirm_four_answers",
        area="sheets",
        prepare=_answers("four", 1280),
        checks=(
            "Four answers in a 1280 px window stand side by side in one row, quietest on the left and "
            "the filled one on the right. Each is as wide as its words (and its size hint), none "
            "squeezed, and every one is inside the card. The card stays inside the window."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.confirm_four_answers_narrow",
        area="sheets",
        prepare=_answers("four", 480),
        checks=(
            "Four answers in a 480 px window stand one above the other, one per row in the same order "
            "with the filled one last. Each is as wide as its words, inside the card; the last one is "
            "inside the card's bottom; the card stays inside the window. At 640 and 900 px the answers "
            "are either in one row or stacked, never half and half."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.confirm_three_answers_narrow",
        area="sheets",
        prepare=_answers("three", 480),
        checks=(
            "Three answers in a 480 px window stacked one per row in order, each as wide as its words "
            "and inside the card, at Normal and Large text."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.confirm_two_answers_narrow",
        area="sheets",
        prepare=_answers("two", 480),
        checks=(
            "Skip's question, two answers (Skip without School, Keep School and go on) in a 480 px "
            "window: each as wide as its words and inside the card, side by side or stacked, never "
            "cut."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.manage_account",
        area="sheets",
        prepare=_manage_account,
        checks=_FRAME
        + "Manage account, at Normal and Large text: New password is not drawn over Current password. "
        "Current password's label is above its box, the box is above New password's label, and that "
        "label is above its box; the two boxes do not overlap. A 1 px line sits above the footer.",
        sources=SOURCES + ("desktop/native/settings.py",),
    ),
    Screen(
        id="sheets.manage_account_delete",
        area="sheets",
        prepare=_manage_account_bottom,
        checks=(
            "Manage account scrolled to the bottom: the red Delete whole account action is fully inside "
            "the scrolled area, at least as tall and wide as its size hint (no words cut off), outlined "
            "with its edge in the error colour (checked at the top middle of the button)."
        ),
        sources=SOURCES + ("desktop/native/settings.py",),
    ),
    Screen(
        id="sheets.preview_save_off",
        area="sheets",
        prepare=_preview_save_off,
        checks=(
            "The preview with nothing ticked: the Save button is off, a pale tint with its words in the "
            "text colour at least 7 to 1 on it, with the line 'Select at least one item before saving.' "
            "under it saying why."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.disabled_primary_button",
        area="sheets",
        prepare=_disabled_primary,
        checks=(
            "A visible disabled main button (a Continue in a plain dialog), in light and dark: its "
            "ground is the text colour mixed 12 % into the panel colour, a pale tint rather than a grey "
            "slab, and its words read at least 7 to 1 on that ground."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.unfinished_panel",
        area="sheets",
        prepare=_unfinished(2),
        checks=(
            "The Unfinished panel with two rows, at Normal and Large text: each row's Plan here (tonal) "
            "and Delete (outlined) buttons are whole, at least 36 px tall (40 at Large) with 8 px "
            "above and below their words, at least their words plus 20 px each side wide, and inside "
            "their row. The list is shorter than three rows and has no scroll bar."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.unfinished_panel_many",
        area="sheets",
        prepare=_unfinished(8),
        checks=(
            "The Unfinished panel with eight rows: the list shows about three and a half rows (within "
            "1 px of 3.5 row heights inside its frame) so the fourth row shows it scrolls, and a "
            "scroll bar shows. At Normal and Large text."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.unfinished_panel_styled_late",
        area="sheets",
        prepare=_unfinished_styled_late,
        checks=(
            "The Unfinished panel filled first and dressed in the look after (a look chosen while it is "
            "open): its button is still at least 36 px tall and its size hint tall, and inside its row, "
            "not cut."
        ),
        sources=SOURCES,
    ),
    Screen(
        id="sheets.plan_review_got_it",
        area="sheets",
        prepare=_plan_review,
        checks=(
            "The plan's review panel after a plan: the heading is the toast's sentence 'Placed 2 homework "
            "blocks. 1 with no time yet.' and Got it is the tonal button, not filled in the accent (the "
            "only accent-filled button on the panel is not Got it)."
        ),
        sources=SOURCES,
    ),
    # --- Pages of other areas -------------------------------------------------------------------------------
    Screen(
        id="account.recovery_continue_off",
        area="account",
        prepare=_recovery_continue_off,
        checks=(
            "The recovery codes page before the box is ticked: Continue to my week is off, a pale tint "
            "with its words in the text colour at least 7 to 1 on it, and the line 'Tick the box above "
            "to continue.' under it says why."
        ),
        sources=SOURCES + ("desktop/native/window.py",),
    ),
    Screen(
        id="settings.labels_beside_fields",
        area="settings",
        prepare=_settings_labels,
        checks=(
            "Settings, on the page with the timers: each label sits beside its field, level with the "
            "words inside the field and not with the field's top edge, 4 px above them. For the stepped "
            "numbers (work, preset timer, long break every) the label sits on the number box, between "
            "the minus and the plus. The labels' middles are within 1 px of the boxes'."
        ),
        sources=("desktop/native/settings.py", "desktop/native/widgets.py"),
    ),
    Screen(
        id="setup.problem_under_school_end",
        area="setup",
        prepare=_setup_bad_school_end,
        checks=(
            "Setup's Your week with a bad School End time (3:15a after a 8:30 start): the problem line "
            "takes its own row under End. Start, End and the day chips stay exactly where they were; "
            "End keeps its width; the line is under End and overlaps no other widget."
        ),
        sources=("desktop/native/setup.py", "desktop/native/fields.py"),
    ),
    Screen(
        id="setup.problem_under_activity_end",
        area="setup",
        prepare=_setup_bad_activity_end,
        checks=(
            "Setup's Your week with a bad End time on an activity (Soccer on Tuesday): the problem "
            "line takes its own row under End; Start, End and the day chips stay exactly where they "
            "were, End keeps its width, and the line overlaps no other widget."
        ),
        sources=("desktop/native/setup.py", "desktop/native/fields.py"),
    ),
    Screen(
        id="setup.problem_pushes_the_activities_down",
        area="setup",
        prepare=_setup_bad_school_end_with_an_activity,
        checks=(
            "Setup's Your week with a bad School End time and an activity below: the activity section "
            "has moved down by the line's height (at least its height less 1 px), and the line ends "
            "above the activity section's top. When the problem is fixed the activity goes back to "
            "where it was."
        ),
        sources=("desktop/native/setup.py", "desktop/native/fields.py"),
    ),
]
