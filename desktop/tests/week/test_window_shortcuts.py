"""F1, Ctrl+N and Ctrl+K pressed on the Week: Help opens, Add homework opens, and the command bar lists the
pages and actions a student can reach by typing. How the bar's rows look is a picture
(desktop/tests/pictures/_sheets_g14.py)."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog

from desktop.native.calendar import sunday_due
from desktop.native.command_bar import match_span
from desktop.native.settings import HELP_KEYS, HelpDialog
from desktop.native.widgets import HomeworkDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until

CTRL = Qt.KeyboardModifier.ControlModifier


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-window-shortcuts"])


def quiet(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    wait_until(
        qapp, lambda: not session.busy and not session.dirty and not any(session.client._replies.values())
    )


@pytest.fixture()
def week(qapp: QApplication, window: NativeWindow) -> NativeWindow:
    """The Week with the History essay waiting, and the calendar holding the keyboard."""
    window.resize(1280, 860)
    session = window.session
    session.add_homework(
        {
            "id": "essay",
            "title": "History essay",
            "due": sunday_due(session.week_start),
            "estimate_min": 60,
            "revision": 0,
        }
    )
    session.save()
    quiet(qapp, window)
    window.findChild(QAbstractButton, "viewWeek").click()
    quiet(qapp, window)
    window.week_table.hours.setFocus()
    return window


def test_f1_opens_help_from_the_week(week: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    def show_help(dialog: HelpDialog) -> int:
        opened.append(dialog.windowTitle())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(HelpDialog, "exec", show_help)
    QTest.keyClick(week.week_table.hours, Qt.Key.Key_F1)
    assert opened == ["Help"]


def test_ctrl_n_opens_add_homework_from_the_week(week: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    def look(dialog: HomeworkDialog) -> int:
        opened.append(dialog.title.text())
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(HomeworkDialog, "exec", look)
    QTest.keyClick(week.week_table.hours, Qt.Key.Key_N, CTRL)
    assert opened == [""]


def test_help_lists_f1_and_ctrl_n() -> None:
    assert ("[F1]", "Help") in HELP_KEYS
    assert ("[Ctrl]+[N]", "Add homework") in HELP_KEYS


def test_ctrl_k_lists_help_add_homework_choose_time_and_settings_pages(week: NativeWindow) -> None:
    QTest.keyClick(week.week_table.hours, Qt.Key.Key_K, CTRL)
    bar = week.command_bar
    try:
        words = bar.shown_words()
        assert "Help" in words
        assert "Add homework" in words
        assert "Choose a time…" in words
        assert "Alerts" in words
        assert "This computer" in words
        assert "Edit look…" in words
        assert "Customise…" not in words
    finally:
        bar.close_bar()


def test_typing_choose_finds_choose_a_time(week: NativeWindow) -> None:
    QTest.keyClick(week.week_table.hours, Qt.Key.Key_K, CTRL)
    bar = week.command_bar
    try:
        QTest.keyClicks(bar.input, "choose")
        assert bar.shown_words() == ["Choose a time…"]
    finally:
        bar.close_bar()


def test_typed_letters_pick_out_the_homework_whose_title_they_match(week: NativeWindow) -> None:
    # The letters the row marks are the leading ones of the first word.
    assert match_span("ma", "Math worksheet") == [(0, 2)]
    QTest.keyClick(week.week_table.hours, Qt.Key.Key_K, CTRL)
    bar = week.command_bar
    try:
        QTest.keyClicks(bar.input, "hist")
        rows = [bar.list.item(row).text() for row in range(bar.list.count())]
        assert "History essay" in rows
    finally:
        bar.close_bar()
