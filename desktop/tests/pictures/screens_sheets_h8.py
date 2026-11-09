"""Pictures of the sheets whose look the old block-editor, form-grammar and wording tests checked in code:
the fixed-time editor's buttons and repeat note, the delete and sign-out questions, problem lines, captions
above fields, buttons that fit their words, and the account cards that keep their top.
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import Mock

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout, QWidget

from desktop.native import widgets
from desktop.native.devices import PairDialog, RemoveDialog, SyncService
from desktop.native.fields import ClockField
from desktop.native.settings import AccountDialog, RestoreDialog
from desktop.native.setup import ActivityRow, HomeworkRow
from desktop.native.widgets import (
    AvailabilityDialog,
    BlockDialog,
    ChooseTimeDialog,
    ConfirmSheet,
    HomeworkDialog,
    LateDialog,
    RoutineDialog,
    SchoolHoursDialog,
    SpreadDialog,
)
from desktop.native.window import NativeWindow
from desktop.native.work_windows import WorkWindowsEditor
from desktop.tests.pictures.screen import Screen
from desktop.tests.sheets.support_clock_typing import type_over
from desktop.tests.sheets.support_fixed_time import go_when
from desktop.tests.sheets.support_soccer import soccer
from desktop.tests.window_support import still

WEEK = "2026-10-12"
WIDGETS = ("desktop/native/widgets.py", "desktop/native/fields.py")

CAPTIONS = (
    "Every field has its caption directly above it, and the caption's left edge is within 8 px of its "
    "field's (a stepper's caption lines up with the stepper, not with the number inside it)."
)
BUTTON_WORDS = (
    "No button's words are cut off: every button is at least as wide as its label, in the picture's "
    "design, light or dark, and at Large text."
)


def _essay() -> dict:
    return {"id": "essay", "title": "Essay", "estimate_min": 60, "due": "2026-10-16", "unplanned_min": 60}


def _settled(dialog: QDialog) -> QDialog:
    dialog.show()
    still(dialog)
    return dialog


def _editor_answers(window: NativeWindow) -> QWidget:
    return _settled(BlockDialog(window, soccer(), occurrence_day=3))


def _repeat_note(window: NativeWindow) -> QWidget:
    dialog = BlockDialog(window, day=3, start="17:15", duration_min=30, from_range=True)
    dialog.show()
    go_when(dialog)
    still(dialog)
    return dialog


def _delete_question(window: NativeWindow) -> QWidget:
    return _settled(
        widgets.confirm_sheet(
            window, "Delete fixed time", "Delete Soccer practice? You can undo this.", "Delete"
        )
    )


def _sign_out_question(window: NativeWindow) -> QWidget:
    return _settled(widgets.confirm_sheet(window, "Sign out", "Sure?", "Sign out", danger=False))


def _lone_clock_problem(window: NativeWindow) -> QWidget:
    host = QWidget(window)
    box = QVBoxLayout(host)
    field = ClockField(QTime(9, 0), host)
    field.setFixedWidth(180)
    box.addWidget(field)
    box.addWidget(QLineEdit(host))
    host.resize(400, 200)
    host.show()
    type_over(QApplication.instance(), field, "nope")
    return host


def _time_row_problem(window: NativeWindow) -> QWidget:
    dialog = _settled(BlockDialog(window, soccer(), occurrence_day=3))
    type_over(QApplication.instance(), dialog.end, "08:00")
    return dialog


def _sync() -> Mock:
    sync = Mock(spec=SyncService)
    sync.pair_start.return_value = None
    return sync


def _delete_school(window: NativeWindow) -> QWidget:
    return ConfirmSheet(
        window,
        "Delete School?",
        "Delete School on Thursday 15 Oct only?",
        (
            ("stay", "Cancel", "outlined"),
            ("day", "This day only", ""),
            ("week", "This week only", "tint"),
            ("later", "This week and later", "danger"),
        ),
        default="stay",
    )


def _availability(kind: str | None) -> Callable[[NativeWindow], QWidget]:
    def make(window: NativeWindow) -> QWidget:
        dialog = AvailabilityDialog(window, {})
        dialog.show()
        if kind in ("study", "protected"):
            dialog._open_picker(kind=kind, day=0)
        elif kind == "cutoff":
            dialog.tabs.setCurrentIndex(dialog.tabs.findData("cutoff"))
        still(dialog)
        return dialog

    return make


def _homework_more_details(window: NativeWindow) -> QWidget:
    dialog = HomeworkDialog(window, _essay(), today=WEEK)
    dialog.show()
    dialog.more_details.setChecked(True)
    still(dialog)
    return dialog


SHEETS: tuple[tuple[str, str, Callable[[NativeWindow], QWidget], tuple[str, ...]], ...] = (
    (
        "pair-device",
        "Pair a device",
        lambda w: _settled(PairDialog(w, _sync(), 1)),
        ("desktop/native/devices.py",),
    ),
    (
        "remove-device",
        "Remove a device",
        lambda w: _settled(RemoveDialog(w, "Pixel")),
        ("desktop/native/devices.py",),
    ),
    ("fixed-time", "Edit fixed time", _editor_answers, WIDGETS),
    ("homework", "Edit homework", lambda w: _settled(HomeworkDialog(w, _essay(), today=WEEK)), WIDGETS),
    ("homework-more-details", "Edit homework with More details open", _homework_more_details, WIDGETS),
    ("school-hours", "School hours", lambda w: _settled(SchoolHoursDialog(w)), WIDGETS),
    (
        "choose-time",
        "Choose a time",
        lambda w: _settled(
            ChooseTimeDialog(w, {"id": "essay", "title": "Essay", "duration_min": 45}, WEEK, [0], [], None)
        ),
        WIDGETS,
    ),
    ("running-late", "Running late", lambda w: _settled(LateDialog(w, "You are in class.")), WIDGETS),
    ("spread", "Spread homework", lambda w: _settled(SpreadDialog(w, _essay(), WEEK)), WIDGETS),
    ("routines", "Routines", lambda w: _settled(RoutineDialog(w, {}, [], WEEK)), WIDGETS),
    ("availability", "Availability", _availability(None), WIDGETS),
    (
        "availability-study-picker",
        "Availability with the study-time picker open",
        _availability("study"),
        WIDGETS,
    ),
    (
        "availability-protected-picker",
        "Availability with the protected-time picker open (its Name (optional) field)",
        _availability("protected"),
        WIDGETS,
    ),
    ("availability-cutoff", "Availability on the cut-off tab", _availability("cutoff"), WIDGETS),
    (
        "manage-account",
        "Manage account",
        lambda w: _settled(AccountDialog(w, 4, {"mode": "local", "username": "ada"})),
        ("desktop/native/settings.py",),
    ),
    ("delete-school", "Delete School? with its four answers", lambda w: _settled(_delete_school(w)), WIDGETS),
    (
        "restore",
        "Restore",
        lambda w: _settled(RestoreDialog(w, [], None, {})),
        ("desktop/native/settings.py",),
    ),
)


def _sheet_screen(
    suffix: str, name: str, make: Callable[[NativeWindow], QWidget], sources: tuple[str, ...]
) -> Screen:
    return Screen(
        id=f"sheets.captions-{suffix}",
        area="sheets",
        prepare=make,
        checks=f"{name}. {CAPTIONS} {BUTTON_WORDS}",
        sources=sources,
        main=suffix in {"homework", "delete-school"},
    )


def _setup_row(make: Callable[[], QWidget]) -> Callable[[NativeWindow], QWidget]:
    def prepare(window: NativeWindow) -> QWidget:
        row = make()
        row.setParent(window)
        row.resize(720, 220)
        row.show()
        return row

    return prepare


def _work_windows(window: NativeWindow) -> QWidget:
    editor = WorkWindowsEditor([{"days": [0], "start": "16:00", "end": "18:00"}])
    editor.setParent(window)
    editor.resize(640, 240)
    editor.show()
    return editor


def _account_card(mode: str, with_problem: bool) -> Callable[[NativeWindow], None]:
    def prepare(window: NativeWindow) -> None:
        window._show_page("authPage")
        window._entry_mode = mode
        window._sync_auth_mode()
        if with_problem:
            if mode == "create":
                window.username.setText("ab")
                window.password.setText("short")
                window.create_button.click()
            elif mode == "reset":
                window.recover_button.click()
            else:
                window.sign_in_button.click()
        still(window)

    return prepare


_MODES = (("sign-in", "sign in"), ("create", "create"), ("reset", "reset"))

SCREENS: list[Screen] = [
    Screen(
        id="sheets.fixed-time-editor-answers",
        area="sheets",
        prepare=_editor_answers,
        checks=(
            "Save is the one filled button: its fill differs from the sheet's card. Cancel is plain: its "
            "fill is the card's colour. Delete is words, not a button: also the card's colour. Delete sits "
            "on the buttons' row (its centre within 4 px of Save's vertically) and at the left of both "
            "Save and Cancel."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        main=True,
    ),
    Screen(
        id="sheets.fixed-time-repeat-note",
        area="sheets",
        prepare=_repeat_note,
        checks=(
            'The note "Pick more days to repeat it." sits directly under the day boxes (a gap of 0 to 8 px '
            "below Thursday's box), is exactly as tall as its words (neither floating above a taller box nor "
            "cut off) and, if it does not wrap, is wide enough for them; at normal and at Large text."
        ),
        sources=("desktop/native/widgets.py",),
        main=True,
    ),
    Screen(
        id="sheets.delete-fixed-time-question",
        area="sheets",
        prepare=_delete_question,
        checks=(
            "The Delete answer is filled in the error red of the design's palette (the same red as the "
            "design's error colour); Cancel is plain and not red. Only these two buttons show."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
        main=True,
    ),
    Screen(
        id="sheets.sign-out-question",
        area="sheets",
        prepare=_sign_out_question,
        checks=(
            "The Sign out answer is filled in the accent, not in the error red: signing out destroys nothing."
        ),
        sources=("desktop/native/widgets.py", "desktop/native/look.py"),
    ),
    Screen(
        id="sheets.clock-field-problem",
        area="sheets",
        prepare=_lone_clock_problem,
        checks=(
            'After "nope" is typed into a 180 px time box, its problem line is as wide as the box (180 px), '
            "has no frame or border (transparent background, no padding, zero side margins) and shows the "
            "error colour and its words."
        ),
        sources=("desktop/native/fields.py", "desktop/native/look.py"),
    ),
    Screen(
        id="sheets.time-row-problem",
        area="sheets",
        prepare=_time_row_problem,
        checks=(
            "With 08:00 typed as the end of a 16:00 block, the one problem line sits under Start and End "
            "together: as wide as the whole time row and wider than the End box, with no frame."
        ),
        sources=("desktop/native/fields.py", "desktop/native/widgets.py"),
        main=True,
    ),
    *(_sheet_screen(*sheet) for sheet in SHEETS),
    Screen(
        id="sheets.captions-setup-homework-row",
        area="sheets",
        prepare=_setup_row(lambda: HomeworkRow("2026-10-16")),
        checks=f"Setup's homework row, 720 px wide: its name, minutes and due fields. {CAPTIONS}",
        sources=("desktop/native/setup.py",),
    ),
    Screen(
        id="sheets.captions-setup-activity-row",
        area="sheets",
        prepare=_setup_row(lambda: ActivityRow("Soccer")),
        checks=f"Setup's activity row, 720 px wide: its name and category fields. {CAPTIONS}",
        sources=("desktop/native/setup.py",),
    ),
    Screen(
        id="sheets.captions-work-windows-editor",
        area="sheets",
        prepare=_work_windows,
        checks=(f"The work-windows editor with one row: its start, end and subject fields. {CAPTIONS}"),
        sources=("desktop/native/work_windows.py",),
    ),
    *(
        Screen(
            id=f"sheets.account-card-{slug}{'-problem' if with_problem else ''}",
            area="sheets",
            prepare=_account_card(mode, with_problem),
            checks=(
                f"The {mode} card. "
                + (
                    "A problem is showing: only the first problem line is visible, its field is marked and "
                    "has the keyboard, and the card's top is exactly where it is in sheets.account-card-"
                    f"{slug} (no problem), so the card did not jump. "
                    if with_problem
                    else "No problem shows. This is the reference for the card's top. "
                )
                + CAPTIONS
            ),
            sources=("desktop/native/window.py", "desktop/native/fields.py"),
            main=with_problem and slug == "create",
        )
        for slug, mode in _MODES
        for with_problem in (False, True)
    ),
]
