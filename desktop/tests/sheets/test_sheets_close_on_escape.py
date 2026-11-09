"""Every sheet opens inside its window, Esc closes it without answering, the dim goes, and the keyboard
goes back to where it was. (Where the card sits inside the window is a look: pictures/_sheets_g13.py.)"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QWidget

from desktop.native.look_editor import LEAVE_TITLE, PICKER_HUES, ColourField
from desktop.native.widgets import Dialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import when_open
from desktop.tests.test_look_editor import open_editor

PREVIEW_ROWS = [
    {
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
        "checked": True,
    }
]


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-sheet-escape-test"])


def sheet_over(window: NativeWindow, sheet: QWidget, title: str) -> None:  # noqa: F811
    """What every sheet is: a frameless dialog over a dimmed window with its title and close button, and
    no framed dialog of the system's beside it."""
    assert isinstance(sheet, Dialog) and sheet.sheet, "a sheet, not a window"
    assert sheet.windowFlags() & Qt.WindowType.FramelessWindowHint
    shade = window.findChild(QWidget, "sheetShade")
    assert shade is not None and shade.isVisible()
    heading = sheet.findChild(QLabel, "sheetTitle")
    assert heading is not None and heading.text() == title and heading.isVisible()
    assert sheet.findChild(QPushButton, "sheetClose").isVisible()
    framed = [
        dialog
        for dialog in window.findChildren(QDialog)
        if dialog.isVisible() and not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    ]
    assert framed == [], "no dialog with a window frame of its own"


def escape_closes(
    qapp: QApplication,
    window: NativeWindow,  # noqa: F811
    launch: Callable[[], object],
    title: str,
    anchor: QWidget,
    during: Callable[[Dialog], None] | None = None,
) -> object:
    """Open the sheet with `launch`, check it is a sheet of `title` over `window`, press Esc, and check
    it closed unanswered, the dimming went, and focus is back on `anchor`."""
    window.resize(1280, 800)
    window.activateWindow()
    qapp.processEvents()
    anchor.setFocus()
    qapp.processEvents()
    assert QApplication.focusWidget() is anchor
    seen: dict[str, object] = {}

    def inside(sheet: QDialog) -> None:
        seen["sheet"] = sheet
        sheet_over(window, sheet, title)
        if during is not None:
            during(sheet)
        QTest.keyClick(sheet, Qt.Key.Key_Escape)

    check = when_open(inside)
    result = launch()
    check()
    sheet = seen["sheet"]
    assert sheet.result() == QDialog.DialogCode.Rejected and not sheet.isVisible()
    qapp.processEvents()
    assert not any(shade.isVisible() for shade in window.findChildren(QWidget, "sheetShade"))
    assert QApplication.focusWidget() is anchor, "focus is back where it was"
    return result


def week_anchor(window: NativeWindow) -> QWidget:  # noqa: F811
    return window.findChild(QPushButton, "todayWeek")


def test_availability_is_a_sheet_that_esc_closes(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    escape_closes(qapp, window, window._open_availability, "Study hours", week_anchor(window))


def test_plan_homework_is_a_sheet_that_esc_closes(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    def launch() -> None:
        window._show_preview(
            "Plan homework",
            "History essay keeps its original deadline and progress.",
            PREVIEW_ROWS,
            label="homework",
        )

    escape_closes(qapp, window, launch, "Plan homework", week_anchor(window))


def test_manage_account_is_a_sheet_that_esc_closes(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    escape_closes(qapp, window, window._open_account, "Manage account", week_anchor(window))


def test_the_sign_out_question_is_a_sheet_that_esc_closes_and_stays_signed_in(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    button = window.findChild(QPushButton, "signOut")
    escape_closes(qapp, window, button.click, "Sign out", week_anchor(window))
    assert window.session.account is not None


def test_saving_the_recovery_codes_starts_on_a_sheet_and_esc_never_reaches_the_file_dialog(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def never() -> str:
        raise AssertionError("the file dialog opened")

    monkeypatch.setattr(window, "_pick_recovery_file", never)
    path = escape_closes(
        qapp, window, window._choose_recovery_file, "Save recovery codes", week_anchor(window)
    )
    assert path == ""


def test_the_accent_picker_is_a_sheet_that_esc_closes_and_puts_the_colour_back(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    _page, editor = open_editor(qapp, window)
    field = editor.findChild(ColourField, "lookColour-accent")
    tried: list[str] = []
    field.picked.connect(tried.append)
    before = field._colour

    def try_one(sheet: Dialog) -> None:
        sheet.dots[6].click()

    escape_closes(qapp, window, field.swatch.click, "Any colour", field.swatch, try_one)
    assert tried[-1] == before and tried[0] == PICKER_HUES[1], "tried live, then put back"


def test_leaving_the_look_editor_asks_on_a_sheet_that_esc_closes_and_stays(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    _page, editor = open_editor(qapp, window)
    answer = escape_closes(qapp, window, editor.ask_leave, LEAVE_TITLE, editor.back)
    assert answer is None, "Esc stays in the editor"
