"""The signed-in Material window the shell tests (and the files that import `window` from
test_material_window.py) start from: the light app, School on weekday mornings and a History essay
planned for Thursday 18:45, the clock at its start (Thursday 19:00).

`window` is the module-wide one for read-only tests and for the older files that import it;
`material_window` is a fresh one per test, for a test that changes anything.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from desktop.native.calendar import sunday_due
from desktop.native.window import NativeWindow
from desktop.tests.light_app import LightWindows
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import look_file

SCHOOL_LIGHT = "#e4ebf7"
HOUR_ROW = 56
FALLBACK = "Material 3 could not open, so FlexWeek is showing the other styles. Your week is unchanged."
NIGHT = {
    "name": "Night study",
    "base": "paper",
    "accent": "sea",
    "colours": {"page": "#1e2430", "card": "#262d3b", "text": "#e8ecf2", "line": "#394255"},
    "categories": {"class": {"hue": 140}},
    "corners": 4,
    "heading_font": "mono",
    "text_scale": 1.2,
}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-material-window"])
    yield application


def settle(qapp: QApplication, made: NativeWindow) -> None:
    """The save and the refreshes it starts have all landed."""
    session = made.session
    wait_until(
        qapp, lambda: not session.busy and not session.dirty and not any(session.client._replies.values())
    )


def seed_week(qapp: QApplication, made: NativeWindow) -> None:
    """School Monday to Friday 08:00 for 390 minutes, and the History essay as one hour on Thursday at
    18:45 (the clock's day, an hour before it ends)."""
    wait_until(qapp, lambda: made.session.preferences is not None)
    session = made.session
    session.add_block(
        {
            "id": "school",
            "title": "School",
            "kind": "locked",
            "category": "class",
            "start": "08:00",
            "duration_min": 390,
            "days": [0, 1, 2, 3, 4],
        }
    )
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
    settle(qapp, made)
    work = next(block for block in session.blocks if block.get("assignment_id") == "essay")
    work.update({"start": "18:45", "days": [3], "duration_min": 60})
    session.add_block(work)
    session.save()
    settle(qapp, made)


@pytest.fixture(scope="module")
def window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[NativeWindow]:
    """Signed in on the light app, clock at Thursday 19:00, School and the History essay seeded. One
    window for the whole module: a test that changes something uses `material_window`."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path_factory.mktemp("material"))
    try:
        made = windows.open((1280, 800))
        seed_week(qapp, made)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            windows.close()
        look_file().unlink(missing_ok=True)


@pytest.fixture()
def material_window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """A window of its own for this test, with the same seeded week as `window`."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open((1280, 800))
        seed_week(qapp, made)
        yield made
    finally:
        windows.close()
