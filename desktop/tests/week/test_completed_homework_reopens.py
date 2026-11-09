"""A homework marked finished stays finished after a reload, and can be reopened."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.logic_support import essay, settled
from desktop.tests.window_support import qapp  # noqa: F401


def test_completed_homework_can_be_reopened_after_a_reload(qapp: QApplication, window: NativeWindow) -> None:
    session = window.session
    session.add_homework(essay(session))
    session.save()
    settled(qapp, session)
    session.complete_homework("essay")
    session.save()
    settled(qapp, session)
    session.reload()
    settled(qapp, session)
    assert session.assignments["essay"]["completed"] is True
    payload = session.week_file()
    assert payload["assignments"][0]["id"] == "essay"
    assert payload["blocks"][0]["assignment_id"] == "essay"
    session.complete_homework("essay", False)
    session.save()
    settled(qapp, session)
    assert session.assignments["essay"]["completed"] is False
