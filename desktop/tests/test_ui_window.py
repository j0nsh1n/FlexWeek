"""The native window driven the way a student drives it, against a real local API.

Dialogs are modal, so a test scripts what the student does inside exec() and lets the window's own
slot read the result. Expected behaviour comes from the web client, the reference implementation.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton

    from desktop.native.widgets import BlockDialog
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer

PASSWORD = "a-long-test-password"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    # The window reads flexweek-look.json from the user data folder. Test mode points Qt at a scratch
    # location, so these tests neither read nor write the look saved on this machine.
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-window-test"])
    yield application


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def settled(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def on_page(window: NativeWindow, name: str) -> bool:
    return window._stack.currentWidget().objectName() == name


@pytest.fixture()
def registering(qapp: QApplication, tmp_path: Path) -> Iterator[NativeWindow]:
    """A window that has just created an account and is showing the recovery codes."""
    server = LocalServer(tmp_path / "flexweek.db", serve_frontend=False)
    server.start()
    window = NativeWindow(server.origin)
    window.show()
    try:
        window.username.setText("ui_student")
        window.password.setText(PASSWORD)
        window.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: on_page(window, "recoveryPage"))
        yield window
    finally:
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        qapp.processEvents()
        server.stop()


@pytest.fixture()
def window(qapp: QApplication, registering: NativeWindow) -> NativeWindow:
    """Signed in, on the week page, with preferences loaded."""
    registering.recovery_ack.setChecked(True)
    registering.recovery_continue.click()
    wait_until(qapp, lambda: on_page(registering, "weekPage") and not registering.session.busy)
    wait_until(qapp, lambda: registering.session.preferences is not None)
    return registering


def school() -> dict:
    return {"id": "school", "title": "School", "kind": "locked", "category": "class",
            "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]}


def saved(qapp: QApplication, window: NativeWindow, *blocks: dict) -> None:
    for block in blocks:
        window.session.add_block(block)
    window.session.save()
    settled(qapp, window)


def student(dialog: QDialog, monkeypatch: pytest.MonkeyPatch, steps: Callable[[], None]) -> None:
    """Stand in for the student while the dialog is open, then return as exec() would."""

    def run() -> int:
        dialog.show()
        steps()
        return dialog.result()

    monkeypatch.setattr(dialog, "exec", run, raising=False)


def test_this_day_only_plus_missed_marks_that_one_day_and_saves(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "This day only" gives Wednesday a new id. The replan was asked for the old id and did nothing,
    and the window returned before saving, so the split stayed an unsaved draft."""
    saved(qapp, window, school())
    dialog = BlockDialog(window, window.session.blocks[0], occurrence_day=2)

    def steps() -> None:
        dialog.scope_occurrence.setChecked(True)
        dialog.missed.setChecked(True)
        dialog.accept()

    student(dialog, monkeypatch, steps)
    window._commit_block(dialog)
    settled(qapp, window)
    by_days = {tuple(block["days"]): block for block in window.session.blocks}
    assert sorted(by_days) == [(0, 1, 3, 4), (2,)]
    # The API leaves missed_days out of a block that has none.
    assert by_days[(2,)].get("missed_days") == [2]
    assert by_days[(0, 1, 3, 4)].get("missed_days") is None
    assert window.session.revision == 2, "the split and the missed day reached the server"
