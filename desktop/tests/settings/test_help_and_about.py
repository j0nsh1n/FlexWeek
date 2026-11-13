"""Help and About, opened from More: what each says, and Help's fade at a scrolling edge.

Their sizes, the thin scroll bar, the fade's drawing and every line fitting at Large text are the
pictures settings.help_sheet, settings.help_sheet_large_text, settings.help_scrolling_sheet and
settings.help_fade_edge.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QScrollArea, QWidget

from desktop.native import settings
from desktop.native.look import sanitize_look
from desktop.native.version import VERSION
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import host, qapp  # noqa: F401


def test_about_gives_the_version_what_flexweek_is_and_opens_the_folder_its_data_lives_in(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It showed the folder as a path to read and copy; a student only wants to look inside it."""
    wait_until(qapp, lambda: window.session.storage_info is not None)
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    dialog = settings.AboutDialog(window, window.session.storage_info, folder)
    said = [label.text() for label in dialog.findChildren(QLabel) if label.text()]
    assert said == [
        "About FlexWeek",
        f"FlexWeek {VERSION}",
        "FlexWeek plans your homework around school, sports and everything else in your week.",
        "Your week is saved on this computer, under this account.",
    ]
    assert dialog.windowTitle() == "About FlexWeek"
    logo = dialog.findChild(QLabel, "aboutLogo")
    assert logo is not None and not logo.pixmap().isNull(), "the logo beside the name"
    opened: list[QUrl] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url) or True))
    button = dialog.findChild(QPushButton, "aboutOpenFolder")
    assert button.text() == "Open folder"
    button.click()
    assert opened == [QUrl.fromLocalFile(folder)]


def test_about_on_a_server_names_the_server_and_has_no_folder_to_open(
    qapp: QApplication, host: QWidget
) -> None:
    dialog = settings.AboutDialog(host, {"mode": "hosted", "origin": "https://plans.example.org"}, "/nowhere")
    said = [label.text() for label in dialog.findChildren(QLabel)]
    assert said[-1] == (
        "Your week is saved on your FlexWeek server, https://plans.example.org, under this account."
    )
    assert dialog.findChild(QPushButton, "aboutOpenFolder") is None


def test_help_explains_each_screen_and_the_keys_and_promises_nothing(
    qapp: QApplication, host: QWidget
) -> None:
    """Its first line was "A tutorial and short guides are coming in a later version"."""
    dialog = settings.HelpDialog(host)
    rows = [row.accessibleName() for row in dialog.findChildren(QWidget, "helpKey")]
    said = "\n".join([*(label.text() for label in dialog.findChildren(QLabel)), *rows])
    assert "tutorial" not in said.lower() and "coming" not in said.lower()
    for line in (
        "Day",
        "One day hour by hour, with homework that isn't placed yet beside it, ready to drag in.",
        "Week",
        "Seven days from the day your week starts on: drag a block to move it, or drag across empty time "
        "to add one.",
        "Month",
        "Each date's blocks and the homework due that day; click a date to open it in Day.",
        "My day",
        "What is on now and what comes next, to follow once your plan is made.",
        "Ctrl+K",
        "Command bar",
        "Ctrl+Shift+F",
        "Quick focus",
        "Ctrl+Z",
        "Undo",
        "Ctrl+Y or Ctrl+Shift+Z",
        "Esc while dragging",
        "Put the block back where it was",
    ):
        assert line in said, line
    assert dialog.windowTitle() == "Help"
    cards = dialog.findChildren(QFrame, "helpCard")
    assert [card.findChild(QLabel, "helpScreenName").text() for card in cards] == [
        name for name, _words in settings.HELP_SCREENS
    ]


def test_help_draws_each_shortcut_as_keycaps(qapp: QApplication, host: QWidget) -> None:
    """Each key its own cap, and the words between keys plain, so Ctrl+K reads as two keys."""
    dialog = settings.HelpDialog(host)
    rows = dialog.findChildren(QWidget, "helpKey")
    said = [settings.keys_words(key) for key, _what in settings.help_keys(True, False)]
    assert [row.accessibleName() for row in rows] == said

    def parts(row: QWidget) -> list[tuple[str, str]]:
        return [(label.objectName(), label.text()) for label in row.findChildren(QLabel)]

    assert parts(rows[3]) == [("helpKeycap", "F1")]
    assert parts(rows[4]) == [("helpKeycap", "Ctrl"), ("helpKeyJoin", "+"), ("helpKeycap", "N")]
    assert parts(rows[5]) == [("helpKeycap", "Ctrl"), ("helpKeyJoin", "+"), ("helpKeycap", "K")]
    assert parts(rows[1]) == [("helpKeycap", "B"), ("helpKeyJoin", "or"), ("helpKeycap", "Esc")]
    assert parts(rows[-1]) == [("helpKeycap", "Esc"), ("helpKeyJoin", "while dragging")]


def test_help_shows_a_fade_only_at_an_edge_with_more_words_past_it(
    qapp: QApplication, window: NativeWindow
) -> None:
    knobs = {**window._look.get("knobs", {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()
    # A sheet is as tall as its window lets it be; in a short one, Help scrolls.
    window.resize(1280, 560)
    dialog = settings.HelpDialog(window)
    dialog.show()
    qapp.processEvents()
    area = dialog.findChild(QScrollArea, "helpScroll")
    bar = area.verticalScrollBar()
    top, bottom = dialog.fades
    assert bar.maximum() > 0, "Help scrolls at this height"
    assert (top.isVisible(), bottom.isVisible()) == (False, True)
    bar.setValue(bar.maximum())
    qapp.processEvents()
    assert (top.isVisible(), bottom.isVisible()) == (True, False)
    bar.setValue(bar.maximum() // 2)
    qapp.processEvents()
    assert (top.isVisible(), bottom.isVisible()) == (True, True)
    dialog.close()
