"""Screens for the notice, the block menu's red Delete, Ctrl+K and the dim behind a sheet."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from backend.tests.fake_clock import CLOCK
from desktop.native.command_bar import Command
from desktop.native.look import resolved_palette
from desktop.native.menus import Menu, menu_colours
from desktop.native.motion import settle
from desktop.native.widgets import BlockDialog, HomeworkDialog, SheetShade
from desktop.native.window import NativeWindow
from desktop.tests.pictures.screen import Screen
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_drag import press_drag
from desktop.tests.window_support import still

SCHOOL = {
    "id": "school",
    "title": "School",
    "kind": "locked",
    "category": "class",
    "start": "08:00",
    "duration_min": 390,
    "days": [0, 1, 2, 3, 4],
}


def _saved(window: NativeWindow) -> None:
    session = window.session
    wait_until(None, lambda: not session.busy and not session.dirty)


def _week_with_school(window: NativeWindow, width: int = 1280, height: int = 860) -> None:
    """The classic Week with School on weekdays, the clock at Thursday 10:00."""
    window.resize(width, height)
    window._layout = {"main": "classic", "day": "one", "options": {}}
    session = window.session
    session.add_block(dict(SCHOOL))
    session.save()
    _saved(window)
    CLOCK.set(CLOCK.now().replace(hour=10, minute=0))
    window.findChild(QAbstractButton, "viewWeek").click()
    _saved(window)
    QApplication.processEvents()


def _notice(text: str, button: str, width: int = 1280) -> object:
    def prepare(window: NativeWindow) -> None:
        _week_with_school(window, width)
        window._set_notice(text, button, (lambda: None) if button else None)
        QApplication.processEvents()
        still(window.toast, window.toast.button)

    return prepare


def _delete_row(window: NativeWindow) -> QWidget:
    pack, dark, accent = window._look_inputs()
    palette = resolved_palette(pack, dark, window._look, accent)
    menu = Menu(window)
    menu.set_colours(menu_colours(palette, lifted=False))
    menu.add("Open", "pencil")
    menu.addSeparator()
    menu.add("Delete", "trash", danger=True)
    menu.popup(window.mapToGlobal(QPoint(100, 100)))
    QApplication.processEvents()
    return menu


def _bar_open(window: NativeWindow, width: int = 1280, height: int = 860) -> QWidget:
    _week_with_school(window, width, height)
    window.week_table.hours.setFocus()
    window._open_command_bar()
    bar = window.command_bar
    QApplication.processEvents()
    settle(bar)
    settle(bar.box)
    return bar.box


def _bar_with_highlight(window: NativeWindow) -> QWidget:
    _week_with_school(window)
    bar = window.command_bar
    bar.open(
        [
            Command(
                "plan", "Plan my homework after school on Friday afternoon", group="Homework", keys="Ctrl+K"
            )
        ]
    )
    QTest.keyClicks(bar.input, "p")
    QApplication.processEvents()
    settle(bar)
    settle(bar.box)
    return bar.box


def _bar_tall(window: NativeWindow) -> QWidget:
    # Tall enough for every command, Settings' group included.
    return _bar_open(window, 1280, 1200)


def _bar_short(window: NativeWindow) -> QWidget:
    return _bar_open(window, 1280, 460)


@contextlib.contextmanager
def _sheets_stay_open(kind: type) -> Iterator[list]:
    """While active, a sheet of `kind` shows and stays open instead of running its own loop."""
    opened: list = []
    real = kind.exec

    def show_only(dialog: object) -> int:
        dialog.show()
        opened.append(dialog)
        return 0

    kind.exec = show_only
    try:
        yield opened
    finally:
        kind.exec = real


def _dimmed(window: NativeWindow) -> None:
    for child in window.children():
        if isinstance(child, SheetShade):
            settle(child)
    still(window)


def _add_sheet(window: NativeWindow) -> None:
    _week_with_school(window)
    with _sheets_stay_open(HomeworkDialog):
        window._add_homework()
    _dimmed(window)


def _drag_sheet(window: NativeWindow) -> None:
    _week_with_school(window)
    hours = window.week_table.hours
    hours.reveal(3, 15 * 60, 18 * 60)
    QApplication.processEvents()
    with _sheets_stay_open(BlockDialog) as opened:
        press_drag(hours, 3, 16 * 60, 17 * 60)
        wait_until(None, lambda: bool(opened))
    _dimmed(window)


SCREENS: list[Screen] = [
    Screen(
        id="week.notice-with-undo",
        area="week",
        prepare=_notice("Moved History essay to Fri 6:00 PM.", "Undo"),
        checks=(
            "the notice sits at the bottom right of the page, clear of the rail on the left, its card "
            "16 px in from the page's corner and wholly inside the window (also in the short edge "
            "window); its words stay on one line and the card is not taller than two lines plus 40 px; "
            "its Undo button sits inside the card; the hours under it are not pushed or resized"
        ),
        sources=("desktop/native/widgets.py", "desktop/native/window.py"),
        main=True,
    ),
    Screen(
        id="week.notice-of-two-lines",
        area="week",
        prepare=_notice("Planned 1 homework block. 1 still needs a time.", "Undo", 1024),
        checks=(
            "a notice whose words wrap onto two lines grows its pill to fit them: no line is cut at the "
            "top or bottom, the pill is at least 44 px tall, with 10 px above and below the words and "
            "16 px at the sides, and the Undo button stays inside the pill"
        ),
        sources=("desktop/native/widgets.py",),
    ),
    Screen(
        id="week.notice-without-button",
        area="week",
        prepare=_notice("Moved it.", ""),
        checks="a short notice with no button is still a pill at least 44 px tall",
        sources=("desktop/native/widgets.py",),
    ),
    Screen(
        id="week.block-menu-delete-row",
        area="week",
        prepare=_delete_row,
        checks=(
            "in a block's menu the Delete row is drawn in the error red and not in the text colour, "
            "and the other row (Open) is drawn in the text colour and not in red; a line sets the "
            "delete apart"
        ),
        sources=("desktop/native/menus.py",),
    ),
    Screen(
        id="week.command-bar-open",
        area="week",
        prepare=_bar_open,
        checks=(
            "Ctrl+K's box is 560 px wide, centred left to right on the window and in its top third; the "
            "window behind it is dimmed 40 percent black; the box is lifted with the large shadow"
        ),
        sources=("desktop/native/command_bar.py", "desktop/native/look.py"),
        main=True,
    ),
    Screen(
        id="week.command-bar-highlighted-row",
        area="week",
        prepare=_bar_with_highlight,
        checks=(
            "a row whose words are highlighted for what was typed keeps 56 px clear of the key caps at "
            "its right edge, as unmatched text does: no text or accent colour reaches that strip"
        ),
        sources=("desktop/native/command_bar.py",),
    ),
    Screen(
        id="week.command-bar-every-row",
        area="week",
        prepare=_bar_tall,
        checks=(
            "in a window tall enough for every command the list shows every row at once with no scroll "
            "bar; the chosen row is tinted with the accent (not the grey of a row under the pointer); "
            "each key (for example Week) is drawn in a cap with an edge"
        ),
        sources=("desktop/native/command_bar.py",),
    ),
    Screen(
        id="week.command-bar-in-a-short-window",
        area="week",
        prepare=_bar_short,
        checks=(
            "in a window shorter than the list, the list scrolls under the app's thin overlay bar and "
            "the box stays inside the window"
        ),
        sources=("desktop/native/command_bar.py",),
    ),
    Screen(
        id="week.sheet-dim-over-the-week-add-homework",
        area="week",
        prepare=_add_sheet,
        checks=(
            "with the Add homework sheet open the week stays visible under the dim: a point on School "
            "is its colour darkened by 40 percent, not blank or a wrong colour"
        ),
        sources=("desktop/native/widgets.py",),
    ),
    Screen(
        id="week.sheet-dim-over-the-week-drag-created-block",
        area="week",
        prepare=_drag_sheet,
        checks=(
            "with the sheet a drag across free time opened, the week stays visible under the dim: a "
            "point on School is its colour darkened by 40 percent, not blank or a wrong colour"
        ),
        sources=("desktop/native/widgets.py", "desktop/native/hours"),
    ),
]
