# ruff: noqa: F811
"""The update dialog and the release notes it shows: readable words, a short preview, and nothing
installed until a button is pressed."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from desktop.native.settings import UpdateDialog, _first_lines  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-update-dialog-test"])


def test_release_notes_are_readable_rather_than_raw_markdown(qapp: QApplication) -> None:
    """GitHub release bodies are Markdown and a QLabel shows it raw, so "## What changed" and
    "- Alarms make a sound" would appear with their markers."""
    notes = "## What changed\n\n- Alarms make a sound.\n* Splitting works.\n**Bold** matters.\n---\n"
    shown = _first_lines(notes)
    assert "##" not in shown
    assert "**" not in shown
    assert shown.splitlines()[0] == "What changed"
    assert shown.splitlines()[1].startswith("•")
    assert "---" not in shown


def test_the_notes_preview_stops_rather_than_filling_the_screen(qapp: QApplication) -> None:
    assert len(_first_lines("\n".join(f"line {n}" for n in range(50))).splitlines()) == 6


def test_the_update_dialog_does_nothing_until_a_button_is_pressed(qapp: QApplication) -> None:
    """An updater that installs on its own is an updater that restarts the app mid-homework."""
    update = {"version": "9.9.9", "asset": "a", "url": "u", "checksum_url": "c", "notes": ""}
    dialog = UpdateDialog(None, update, "0.13.0")
    assert dialog.choice == "later"
    assert dialog.skip_this is False
    dialog.findChild(QPushButton, "updateSkip").click()
    assert dialog.skip_this is True
