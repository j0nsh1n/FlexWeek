# ruff: noqa: F811

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QDate, QRect, Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyleOptionViewItem

from desktop.native.hours.rail import BOOK_GAP, SPACING, TITLE_GAP
from desktop.native.look import resolved_palette, sanitize_look
from desktop.native.weekmodel import Waiting
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import CREATE, RESET, SIGN_IN, NativeWindow
from desktop.tests.test_week_side import seeded
from desktop.tests.window_support import qapp, server, signed_out, window  # noqa: F401


@pytest.mark.parametrize(
    ("mode", "field_name"),
    [(SIGN_IN, "password"), (CREATE, "password"), (RESET, "recovery_code")],
)
def test_enter_submits_the_active_auth_card_and_focuses_its_first_problem(
    qapp, signed_out: NativeWindow, mode: str, field_name: str
) -> None:
    card = signed_out
    card._entry_mode = mode
    card._sync_auth_mode()
    card.username.setText("jo" if mode == CREATE else "")
    card.password.setText("short" if mode == CREATE else "anything")
    card.recovery_code.setText("")
    card.new_recovery_password.setText("")
    field = getattr(card, field_name)
    field.setFocus()

    QTest.keyClick(field, Qt.Key.Key_Return)
    qapp.processEvents()

    assert card.focusWidget() is card.username
    assert card.username_problem.isVisible()
    enter_problem = card.username.accessibleDescription()

    card._clear_auth_problems()
    card.username.setText("jo" if mode == CREATE else "")
    card.password.setText("short" if mode == CREATE else "anything")
    card.recovery_code.setText("")
    card.new_recovery_password.setText("")
    {SIGN_IN: card.sign_in_button, CREATE: card.create_button, RESET: card.recover_button}[mode].click()
    qapp.processEvents()

    assert card.username.accessibleDescription() == enter_problem
    assert card.focusWidget() is card.username


def test_not_placed_rows_keep_each_open_sessions_length(qapp, window: NativeWindow) -> None:
    rail = window.rail
    rail.set_waiting(
        (
            Waiting("hist-1", "History essay", "assignments", 60, "history", None, ""),
            Waiting("hist-2", "History essay", "assignments", 30, "history", None, ""),
        ),
        {"history": 90},
    )

    assert [chip.length for chip in rail.chips()] == ["1 h", "30 min"]
    assert sum((60, 30)) == 90


def test_focus_rows_allocate_height_for_long_titles_without_overlap(qapp, window: NativeWindow) -> None:
    rail = window.rail
    rail.set_tasks(
        [
            {
                "id": "long",
                "day": 0,
                "start": "19:00",
                "title": (
                    "A long history essay title with many words that must wrap across lines before focus"
                ),
            },
            {"id": "short", "day": 1, "start": "19:00", "title": "Math"},
        ],
        0,
    )
    qapp.processEvents()

    tasks = rail.tasks
    rows = [tasks.visualItemRect(tasks.item(index)) for index in range(tasks.count())]
    delegate = tasks.itemDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, tasks.viewport().width(), 0)
    lines, _below, _timing = delegate.row_lines(tasks.indexFromItem(tasks.item(0)), option.rect.width())
    assert len(lines) > 1
    expected = delegate.sizeHint(option, tasks.indexFromItem(tasks.item(0))).height()
    assert tasks.item(0).sizeHint().height() >= expected
    assert rows[0].height() >= expected
    assert rows[0].height() > 30
    assert rows[1].top() > rows[0].bottom()
    assert tasks.height() >= sum(tasks.item(index).sizeHint().height() for index in range(tasks.count()))


LONG_FOCUS_TASKS = [
    {
        "id": "long",
        "day": 0,
        "start": "19:00",
        "title": "A long history essay title with many words that must wrap",
    },
    {
        "id": "next",
        "day": 0,
        "start": "20:00",
        "title": "Another long chemistry report title that must also wrap",
    },
    {"id": "short", "day": 1, "start": "19:00", "title": "Math"},
]


def show_wide_rail(qapp, window: NativeWindow) -> None:
    """The week as the real app has it, wide enough that the rail stands beside it, and no focus list
    yet. The offscreen default folds the rail and a folded rail hides the list, so the list is never
    measured at its real width there."""
    seeded(qapp, window)
    window.rail.set_tasks([], 0)
    qapp.processEvents()
    assert window.isVisible()
    assert window.rail.isVisible()
    assert not window.rail.folded
    assert not window.rail.focus.isVisible()


def assert_focus_rows_hold_their_text(rail) -> None:
    """Each row is at least as tall as the lines it paints at the list's width right now, and no two
    rows' rectangles meet. Heights come from the active font's metrics, not from numbers."""
    tasks = rail.tasks
    delegate = tasks.itemDelegate()
    body, _small = rail.fonts()
    line = QFontMetricsF(body).lineSpacing()
    width = tasks.viewport().width()
    rects = [tasks.visualItemRect(tasks.item(row)) for row in range(tasks.count())]
    for row, rect in enumerate(rects):
        index = tasks.indexFromItem(tasks.item(row))
        lines, _below, _timing = delegate.row_lines(index, width)
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, width, 0)
        assert rect.height() >= line * len(lines), (row, rect.height(), len(lines))
        assert rect.height() >= delegate.sizeHint(option, index).height(), (row, rect.height())
        assert tasks.item(row).sizeHint().height() >= delegate.sizeHint(option, index).height(), row
        assert len(lines) == 1 or rect.height() > 30
        assert rect.width() == width
    for above, below in zip(rects, rects[1:], strict=False):
        assert not above.intersects(below)
    assert tasks.height() >= sum(rect.height() for rect in rects)
    assert tasks.height() >= sum(tasks.item(row).sizeHint().height() for row in range(tasks.count()))


def test_focus_rows_hold_wrapped_titles_when_the_list_first_appears(qapp, window: NativeWindow) -> None:
    show_wide_rail(qapp, window)
    rail = window.rail
    # A list never shown still has the width of wherever it was first laid out, wider than the rail.
    rail.tasks.viewport().resize(window.width(), rail.tasks.viewport().height())
    assert rail.tasks.viewport().width() == window.width()

    rail.set_tasks(LONG_FOCUS_TASKS, 0)
    qapp.processEvents()

    tasks = rail.tasks
    assert tasks.isVisible()
    assert tasks.viewport().width() < window.width()
    wrapped = [
        len(tasks.itemDelegate().row_lines(tasks.indexFromItem(tasks.item(row)), tasks.viewport().width())[0])
        for row in range(2)
    ]
    assert wrapped == [2, 2]
    assert_focus_rows_hold_their_text(rail)


def test_focus_rows_are_measured_again_when_the_list_width_or_font_changes(
    qapp, window: NativeWindow
) -> None:
    show_wide_rail(qapp, window)
    rail = window.rail
    rail.set_tasks([{"id": "one", "day": 2, "start": "19:00", "title": "Chem lab"}], 0)
    qapp.processEvents()
    tasks = rail.tasks
    index = tasks.indexFromItem(tasks.item(0))
    fitted = tasks.item(0).sizeHint().height()
    assert_focus_rows_hold_their_text(rail)

    # The list narrows without the rail itself resizing, until the title no longer fits beside its time.
    _lines, _below, timing = tasks.itemDelegate().row_lines(index, tasks.viewport().width())
    body, _small = rail.fonts()
    beside = (
        SPACING[1]
        + 16
        + BOOK_GAP
        + QFontMetricsF(body).horizontalAdvance("Chem lab")
        + TITLE_GAP
        + QFontMetricsF(timing).horizontalAdvance(str(index.data(Qt.ItemDataRole.ToolTipRole)))
        + SPACING[1]
    )
    rail.focus.setFixedWidth(int(beside) - 8)
    qapp.processEvents()
    assert tasks.viewport().width() < beside
    assert tasks.item(0).sizeHint().height() > fitted
    assert_focus_rows_hold_their_text(rail)

    # A larger text size re-measures the rows with the larger font.
    before = QFontMetricsF(rail.fonts()[0]).lineSpacing()
    rail.set_look(sanitize_look({"knobs": {"text": "large"}}), resolved_palette("system", False, None))
    qapp.processEvents()
    assert QFontMetricsF(rail.fonts()[0]).lineSpacing() > before
    assert_focus_rows_hold_their_text(rail)


def test_homework_due_date_keys_step_by_day_and_by_week(qapp) -> None:
    dialog = HomeworkDialog(None, today="2026-10-05")
    field = dialog.due.date
    field.setDate(QDate(2026, 10, 9))
    field.setFocus()

    QTest.keyClick(field, Qt.Key.Key_Up)
    assert field.date() == QDate(2026, 10, 10)
    QTest.keyClick(field, Qt.Key.Key_Up)
    assert field.date() == QDate(2026, 10, 11)
    QTest.keyClick(field, Qt.Key.Key_PageDown)
    assert field.date() == QDate(2026, 10, 18)
    QTest.keyClick(field, Qt.Key.Key_Down)
    assert field.date() == QDate(2026, 10, 17)
