"""The notice a change leaves: what the advanced actions say, where it stays and goes, and what it
lets the pointer reach."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox, QLineEdit, QPushButton

from desktop.native.settings import RestoreDialog
from desktop.native.widgets import BlockDialog, PreviewDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import open_light  # noqa: F401
from desktop.tests.week.support_drag import (
    LEFT,
    click,
    qapp,  # noqa: F401
    settled,
    toast,
    window,  # noqa: F401
)
from desktop.tests.window_support import still


def advanced(window: NativeWindow, words: str) -> None:
    """Pick the item under More > Undo, copy and save whose words start with `words`, as a click does."""
    menu = window.more_button.menu()
    menu.aboutToShow.emit()
    inner = next(
        action.menu() for action in menu.actions() if action.menu() and action.text() == "Undo, copy and save"
    )
    next(action for action in inner.actions() if action.text().startswith(words)).trigger()


def test_every_advanced_action_says_what_it_did_when_it_is_done(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Their words went only to the status line at the foot of the window, which nobody watched."""
    days = iter((4, 5))

    def preview(dialog: PreviewDialog) -> int:
        """Put the copy on a free day, which ticks it, and save the preview."""
        dialog.show()
        dialog.findChild(QComboBox, "previewDay0").setCurrentIndex(next(days))
        QTest.mouseClick(dialog.confirm, LEFT)
        return dialog.result()

    def restore(dialog: RestoreDialog) -> int:
        dialog.show()
        QTest.keyClicks(dialog.findChild(QLineEdit, "restoreLabel"), "Before exams")
        QTest.mouseClick(dialog.findChild(QPushButton, "restoreCreate"), LEFT)
        return dialog.result()

    monkeypatch.setattr(PreviewDialog, "exec", preview)
    monkeypatch.setattr(RestoreDialog, "exec", restore)
    # The click that picks Piano opens it too; the student closes it again.
    monkeypatch.setattr(BlockDialog, "exec", lambda dialog: dialog.reject() or dialog.result())
    hours = window.week_table.hours
    hours.reveal(3, 16 * 60, 19 * 60)
    qapp.processEvents()
    click(qapp, hours, hours.point_for(3, 17 * 60 + 15))
    assert window.session.selected_block_id == "piano"
    shown: list[str] = []
    real = window.toast.show_message

    def noted(text: str, *more: object) -> None:
        shown.append(text)
        real(text, *more)

    monkeypatch.setattr(window.toast, "show_message", noted)
    said = []
    for words in (
        "Copy",
        "Paste",
        "Duplicate",
        "Copy Thursday",
        "Undo",
        "Redo",
        "Copies of",
        "Reload this",
    ):
        window.toast.hide()
        shown.clear()
        advanced(window, words)
        settled(qapp, window)
        # Everything the toast said on the way, not only its last words: Duplicate once said "Piano
        # copied" first.
        said.append((words, " / ".join(shown) if shown[1:] else toast(window)))
    assert said == [
        ("Copy", "Piano copied. Choose a destination and paste."),
        ("Paste", "Pasted Piano."),
        ("Duplicate", "Duplicated Piano."),
        ("Copy Thursday", "Thursday · 3 items copied. Choose a destination and paste."),
        ("Undo", "Undid duplicating Piano."),
        ("Redo", "Redid duplicating Piano."),
        ("Copies of", "Saved restore point Before exams."),
        ("Reload this", "Reloaded this week."),
    ]


def test_a_notice_coming_and_going_never_moves_the_hours(qapp: QApplication, window: NativeWindow) -> None:
    """A notice in a row of its own pushed the page down under the pointer, and on a short window put
    the next drop where the hours scroll by themselves. The toast floats over the hours instead."""
    before = window.planner.geometry()
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", lambda: None)
    for _ in range(5):
        qapp.processEvents()
    assert window.toast.isVisible()
    assert window.planner.geometry() == before
    window.toast.hide()
    for _ in range(5):
        qapp.processEvents()
    assert window.planner.geometry() == before


def test_the_notice_sits_in_the_right_half_of_the_page_and_lets_the_pointer_through(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Bottom right, clear of the rail on the left, inside the window at any height (decision 20 of
    0.17), and only its button takes a click: what is under its words still takes a drag."""
    pressed = []
    for height in (860, 600):
        window.resize(1280, height)
        for _ in range(5):
            qapp.processEvents()
        window._set_notice("Moved History essay to Fri 18:00.", "Undo", lambda: pressed.append(True))
        # Past its rise into place.
        still(window.toast, window.toast.button)
        toast, planner = window.toast, window.planner
        card = toast.card.geometry().translated(toast.pos())
        middle = planner.mapTo(window, QPoint(planner.width() // 2, 0)).x()
        assert card.left() > middle, "in the right half of the page, clear of the rail"
        assert toast.geometry().bottom() < window.height(), height
        words = toast.geometry().topLeft() + QPoint(12, toast.height() // 2)
        assert window.childAt(words) is not toast and not toast.isAncestorOf(window.childAt(words))
        assert planner.isAncestorOf(window.childAt(words)), "the words take the hours' clicks"
        button = toast.button
        assert toast.geometry().contains(button.geometry()), "the button sits inside the toast"
        assert window.rect().contains(button.geometry()), "the button is inside the window"
        assert window.childAt(button.geometry().center()) is button
    QTest.mouseClick(window.toast.button, LEFT)
    assert pressed == [True]
    assert not window.toast.isVisible()


def test_the_toast_belongs_to_the_page_it_was_said_on(qapp: QApplication, window: NativeWindow) -> None:
    """Decision 20: "Planned 2 homework blocks." stayed over the focus screen, which has nothing to do
    with planning. Leaving the page takes the toast; coming back does not bring it."""
    window._set_notice("Planned 2 homework blocks.", "Undo", lambda: None)
    qapp.processEvents()
    assert window.toast.isVisible()
    window._open_focus_screen()
    qapp.processEvents()
    assert not window.toast.isVisible() and not window.toast.button.isVisible()
    window._close_focus_screen()
    qapp.processEvents()
    assert not window.toast.isVisible(), "it does not come back with the page"
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", lambda: None)
    window._show_page("weekPage")
    qapp.processEvents()
    assert window.toast.isVisible(), "the page it is on, asked for again, is not leaving"


def test_a_view_switch_keeps_the_toast_and_its_undo(qapp: QApplication, window: NativeWindow) -> None:
    """0.18.5 #97: the Undo toast vanished on the first view switch. It stays through Day, Month, Week
    and My day, until it times out or is used."""
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", lambda: None)
    qapp.processEvents()
    assert window.toast.isVisible()
    for name in ("viewMonth", "viewDay", "viewWeek", "viewMyDay", "viewWeek"):
        QTest.mouseClick(window.findChild(QAbstractButton, name), LEFT)
        settled(qapp, window)
        assert window.toast.isVisible() and window.toast.button.isVisible(), name


def test_a_routine_save_says_nothing_and_a_refusal_says_why(qapp: QApplication, window: NativeWindow) -> None:
    """The status line said "Saved." after every drag. The toast says only what the student needs."""
    window.toast.hide()
    window.session._say("Saving…")
    window.session._say("Saved.")
    window.session._say("Saved preferences.")
    qapp.processEvents()
    assert not window.toast.isVisible()
    window.session._say("Select a block before copying it.")
    qapp.processEvents()
    assert toast(window) == "Select a block before copying it."
