"""A second restore point with the same name is a new backup, not the first one handed back."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_second_restore_point_with_the_same_name_is_a_new_backup(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The first call's operation id was reused, so the server handed back the old point and the second
    backup never captured the newer week."""
    session = window.session
    session.create_restore_point("Before exams")
    wait_until(qapp, lambda: len(session.restore_points) == 1 and not session.busy)
    first = session.restore_points[0]["id"]
    session.create_restore_point("Before exams")
    wait_until(qapp, lambda: len(session.restore_points) == 2 and not session.busy)
    assert session.restore_points[0]["id"] != first
