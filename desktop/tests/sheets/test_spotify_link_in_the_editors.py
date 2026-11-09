"""The Add and Edit sheets for homework and fixed times have no Spotify box (the link lives in
Settings), and an edit keeps a link already stored."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from desktop.native.widgets import BlockDialog, HomeworkDialog
from desktop.tests.sheets.support_dialogs import school

TRACK = "https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-spotify-editors-test"])


def test_add_and_edit_sheets_have_no_spotify_field(qapp: QApplication) -> None:
    added = BlockDialog(None, day=0, start="16:00")
    edited = BlockDialog(None, school(spotify_url=TRACK))
    new_homework = HomeworkDialog(None, None, "2026-09-14")
    old_homework = HomeworkDialog(
        None,
        {
            "id": "math",
            "title": "Math worksheet",
            "due": "2026-09-14T21:00",
            "estimate_min": 45,
            "revision": 0,
            "spotify_url": TRACK,
        },
        "2026-09-14",
    )
    for dialog in (added, edited, new_homework, old_homework):
        assert dialog.findChild(QLineEdit, "blockSpotify") is None
        assert dialog.findChild(QLineEdit, "homeworkSpotify") is None
    assert edited.findChild(QPushButton, "blockMoreDetails") is None


def test_editing_a_fixed_time_keeps_the_spotify_link_already_stored(qapp: QApplication) -> None:
    dialog = BlockDialog(None, school(spotify_url=TRACK))
    dialog.title.setText("School day")
    dialog.accept()
    saved = dialog.block()
    assert saved["title"] == "School day"
    assert saved["spotify_url"] == TRACK


def test_editing_homework_keeps_the_spotify_link_already_stored(qapp: QApplication) -> None:
    dialog = HomeworkDialog(
        None,
        {
            "id": "math",
            "title": "Math worksheet",
            "due": "2026-09-14T21:00",
            "estimate_min": 45,
            "revision": 0,
            "notes": "",
            "links": [],
            "checklist": [],
            "spotify_url": TRACK,
        },
        "2026-09-14",
    )
    assert dialog.more_details.isChecked() is False
    dialog.title.setText("Math worksheet, revised")
    dialog.accept()
    saved = dialog.assignment()
    assert saved["title"] == "Math worksheet, revised"
    assert saved["spotify_url"] == TRACK
