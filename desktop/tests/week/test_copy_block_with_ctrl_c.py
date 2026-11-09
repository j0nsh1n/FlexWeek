"""Ctrl+C on the Week copies the selected block into the app's own clipboard and leaves the system
clipboard alone."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-copy-block"])


def test_ctrl_c_in_the_week_grid_copies_the_block_and_leaves_the_os_clipboard_alone(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The native migration's rule (docs/native-python-migration.md, in git history): "Ctrl/C/V/D never
    touch the OS clipboard"."""
    session = window.session
    session.add_block(
        {"id": "soccer", "title": "Soccer", "kind": "locked", "start": "07:00", "duration_min": 60,
         "days": [0]}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    session.select_block("soccer", 0)
    QGuiApplication.clipboard().setText("the student's own text")
    # Pressed on the week itself, where a block was just clicked: the window's copy, not the system's.
    window.week_table.hours.setFocus()
    QTest.keyClick(window.week_table.hours, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QGuiApplication.clipboard().text() == "the student's own text"
    assert (session.clipboard or {}).get("kind") == "block"
    assert "Soccer" in session.clipboard["label"]
