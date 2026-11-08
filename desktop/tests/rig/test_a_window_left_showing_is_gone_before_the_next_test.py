"""What one test leaves on screen for the next, run in a pytest of its own so the order is known."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

ROOT = Path(__file__).resolve().parents[3]

WINDOWS = '''
import pytest
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

APP = QApplication.instance() or QApplication(["flexweek-windows-between-tests"])
# Held here as a view's own signals hold it, so the window outlives the test that showed it.
KEPT = []


@pytest.fixture(scope="module")
def board():
    shown = QWidget()
    shown.setObjectName("board")
    shown.show()
    yield shown
    shown.hide()


@pytest.fixture(scope="module")
def hidden_board():
    hidden = QWidget()
    yield hidden
    hidden.deleteLater()


def showing():
    return sorted(window.objectName() for window in QApplication.topLevelWidgets() if window.isVisible())


def test_a_view_shown_on_its_own_is_left_showing(board, hidden_board):
    view = QWidget()
    view.setObjectName("stray")
    view.resize(1366, 760)
    view.show()
    child = QWidget(view)
    hidden = QWidget()
    hidden.setObjectName("hidden")
    KEPT.extend((view, child, hidden))
    assert showing() == ["board", "stray"]


def test_the_next_test_finds_only_what_its_module_opened(board, hidden_board):
    assert showing() == ["board"]
    assert isValid(board), "a module fixture's window was deleted"
    assert isValid(hidden_board), "a module fixture's hidden window was deleted"
    assert len(KEPT) == 3, "the preceding test did not retain its widgets"
    assert all(not isValid(widget) for widget in KEPT), "a test's widget was hidden but left alive"
'''

POINTER = '''
from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QWidget

APP = QApplication.instance() or QApplication(["flexweek-pointer-between-tests"])
KEPT = []


def test_a_test_parks_the_pointer_over_a_view_that_lives_on_hidden():
    view = QWidget()
    view.resize(400, 400)
    view.show()
    KEPT.append(view)
    QCursor.setPos(QPoint(200, 200))
    view.hide()
    assert QCursor.pos() == QPoint(200, 200)


def test_the_next_test_starts_with_the_pointer_where_a_new_worker_has_it():
    assert QCursor.pos() == QPoint(10, 10)
'''


def run_in_a_pytest_of_its_own(folder: Path, source: str) -> subprocess.CompletedProcess[str]:
    (folder / "pytest.ini").write_text("[pytest]\n")
    (folder / "test_left.py").write_text(source)
    env = {name: value for name, value in os.environ.items() if not name.startswith("PYTEST_")}
    env.update(PYTHONPATH=str(ROOT), QT_QPA_PLATFORM="offscreen", FLEXWEEK_SILENT="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:xdist",
         "-p", "desktop.tests.conftest", "-c", str(folder / "pytest.ini"), str(folder / "test_left.py")],
        cwd=folder, env=env, capture_output=True, text=True, timeout=120,
    )


def test_a_window_one_test_leaves_showing_is_gone_before_the_next(tmp_path: Path) -> None:
    """Views left showing lay over later tests' windows, and a drag dropped on one of them instead."""
    result = run_in_a_pytest_of_its_own(tmp_path, WINDOWS)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert "2 passed" in result.stdout


def test_where_one_test_leaves_the_pointer_does_not_carry_over_to_the_next(tmp_path: Path) -> None:
    """A pointer left over a view that lives on hidden sent that view's leave first on the next test's
    first move, which took hover off the window under it. Every test starts with the pointer at (10, 10)."""
    result = run_in_a_pytest_of_its_own(tmp_path, POINTER)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert "2 passed" in result.stdout
