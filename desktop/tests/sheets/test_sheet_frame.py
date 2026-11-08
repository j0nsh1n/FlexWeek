# ruff: noqa: F811
"""What makes a dialog a sheet: no window frame of its own, a dimmed window behind it, a title and a
close button in its corner, the keyboard starting where the answer is, and the dim going with it.
How big the card is and where it sits are looks: pictures/_sheets_g13.py."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QScrollArea, QWidget

from desktop.native.settings import AboutDialog, HelpDialog
from desktop.native.widgets import (
    BlockDialog,
    HomeworkDialog,
    LateDialog,
    RoutineDialog,
    SchoolHoursDialog,
    SpreadDialog,
)
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import (
    ESSAY,
    WEEK,
    choose_time,
    shown,
    soccer,
    styled,
    when_open,
)
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-sheet-frame-test"])


def test_the_editors_and_the_seven_others_are_sheets_over_the_dimmed_week(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Add and Edit were sheets; Routines, Help, About, Running late and School hours were windows of
    their own with title bars; Choose a time and Spread, opened from the editors, were windows too."""
    window.resize(1280, 800)
    qapp.processEvents()
    editors = (
        lambda: HomeworkDialog(window, today=WEEK),
        lambda: BlockDialog(window, soccer(), occurrence_day=3),
    )
    others = (
        lambda: RoutineDialog(window, {}, [soccer()], WEEK),
        lambda: HelpDialog(window),
        lambda: AboutDialog(window, {"mode": "local"}, "/nowhere"),
        lambda: LateDialog(window, "Soccer practice"),
        lambda: SchoolHoursDialog(window, None),
        lambda: choose_time(window),
        lambda: SpreadDialog(window, ESSAY, WEEK),
    )
    for make in (*editors, *others):
        dialog = shown(qapp, make())
        name = dialog.windowTitle()
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint, f"{name}: no window frame of its own"
        shade = window.findChild(QWidget, "sheetShade")
        assert shade is not None and shade.isVisible(), f"{name}: the week behind is dimmed"
        assert shade.geometry() == window.rect(), f"{name}: the dim covers the whole window"
        if make in editors:
            assert QApplication.focusWidget() is dialog.title, "typing starts in the title"
            primary = dialog._save
            if dialog.windowTitle() == "Add homework":
                assert primary.text() == "Next" and primary.isDefault()
            else:
                assert primary.text() == "Save" and primary.isDefault(), "Enter saves"
        # Still a modal dialog to Qt, so the week's keys wait for it and the rig can find it.
        seen: list[object] = []
        dialog.hide()
        check = when_open(seen.append)
        dialog.exec()
        check()
        assert seen == [dialog], name
        qapp.processEvents()
        assert not any(item.isVisible() for item in window.findChildren(QWidget, "sheetShade")), (
            f"{name}: the dimming goes with the sheet"
        )
        free(dialog)
    assert window.findChild(QWidget, "sheetShade") is None


@pytest.mark.parametrize(
    ("make", "title"),
    [
        (lambda parent: HomeworkDialog(parent, today=WEEK), "Add homework"),
        (
            lambda parent: HomeworkDialog(
                parent, {"id": "e", "title": "Essay", "due": WEEK, "estimate_min": 60, "revision": 1}
            ),
            "Edit homework",
        ),
        (lambda parent: BlockDialog(parent, day=3, start="17:00"), "Add fixed time"),
        (lambda parent: BlockDialog(parent, soccer(), occurrence_day=3), "Edit fixed time"),
        (choose_time, "Choose a time"),
        (lambda parent: SpreadDialog(parent, ESSAY, WEEK), "Spread homework"),
    ],
)
def test_a_sheet_says_what_it_is_and_closes_from_its_corner(
    qapp: QApplication, make: Callable[[QWidget], QDialog], title: str
) -> None:
    """No sheet had a title, and one without a window frame had nothing to close it but Cancel."""
    parent, _palette = styled(qapp)
    dialog = shown(qapp, make(parent))
    heading = dialog.findChild(QLabel, "sheetTitle")
    assert heading is not None and heading.text() == title and heading.isVisible()
    close = dialog.findChild(QPushButton, "sheetClose")
    assert close.isVisible() and close.accessibleName() == "Close"
    close.click()
    assert dialog.result() == QDialog.DialogCode.Rejected and not dialog.isVisible()
    free(dialog)
    free(parent)


def test_add_homeworks_answers_stay_outside_the_scrolled_body(qapp: QApplication) -> None:
    """Save and Cancel are not part of what scrolls, with a line above them."""
    parent, _palette = styled(qapp)
    dialog = shown(qapp, HomeworkDialog(parent, today=WEEK))
    line = dialog.findChild(QWidget, "sheetFooterLine")
    area = dialog.findChild(QScrollArea, "homeworkScroll")
    buttons = dialog.findChild(QWidget, "dialogButtons")
    assert line is not None and line.isVisible()
    assert not area.isAncestorOf(buttons)
    assert not area.isAncestorOf(line)
    free(dialog)
    free(parent)
