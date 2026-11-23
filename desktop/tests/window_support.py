"""A signed-in window on the real service, for tests that drive the window as a student does."""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QStandardPaths
from PySide6.QtWidgets import QApplication, QWidget

from backend.storage import initialize
from desktop.native.window import NativeWindow
from desktop.tests.logic_support import past_recovery, past_setup, sign_up
from desktop.tests.waiting import wait_until  # noqa: F401

PASSWORD = "a-long-test-password"
USERNAME = "words_student"


def turn_on_letter_keys() -> None:
    """Letter keys is a saved setting that starts off. Write it the way Settings does, in the look file's
    material object, which both looks read."""
    path = look_file()
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError):
        stored = {}
    stored["material"] = {**stored.get("material", {}), "letters": True}
    path.write_text(json.dumps(stored))


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-words-test"])
    yield application


def settled(qapp: QApplication, window: NativeWindow) -> None:
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)


def free(widget: QWidget | NativeWindow) -> None:
    """Delete a widget now. Left to the garbage collector, a widget a failed test still held went in
    the middle of a later test's event loop, and Qt crashed. The app window is a controller that owns its
    own windows (Material's Qt Quick window, the draw-error page), so they are deleted with it."""
    for face in widget._faces() if isinstance(widget, NativeWindow) else ():
        face.hide()
        face.deleteLater()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


@pytest.fixture()
def host(qapp: QApplication) -> Iterator[QWidget]:
    """A parent for dialogs a test makes on their own, freed when the test ends, pass or fail."""
    made = QWidget()
    yield made
    free(made)


@pytest.fixture()
def database(qapp: QApplication, tmp_path: Path) -> Path:
    """The saved data the window opens on, as the app opens it at start."""
    path = tmp_path / "flexweek.db"
    initialize(path)
    return path


def look_file() -> Path:
    """The device look file, shared by every suite through ~/.qttest; a test that saved a knob would
    otherwise hand it to the next."""
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


@pytest.fixture()
def signed_out(qapp: QApplication, database: Path) -> Iterator[NativeWindow]:
    look_file().unlink(missing_ok=True)
    window = NativeWindow(database)
    window.show()
    try:
        yield window
    finally:
        with contextlib.suppress(RuntimeError):
            window.session.client.reset()
        window.hide()
        free(window)


@pytest.fixture()
def window(qapp: QApplication, signed_out: NativeWindow) -> NativeWindow:
    """Signed in on the week page, setup skipped, preferences loaded."""
    sign_up(qapp, signed_out, USERNAME, PASSWORD)
    past_recovery(qapp, signed_out)
    past_setup(qapp, signed_out)
    return signed_out
