"""Focus minutes credited while a save is under way are kept, not overwritten by the save's answer."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.tests.fake_clock import FakeClock  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402,F401
from desktop.tests.logic_support import essay, place_on_monday  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-focus-credit-test"])


def settled(qapp: QApplication, made: NativeWindow) -> None:
    session = made.session
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and not session.dirty
            and not session.dirty_assignments
            and not getattr(session.client, "pending", 0)
        ),
    )


def test_focus_time_finished_during_a_save_is_kept(
    qapp: QApplication, open_light: Callable[..., NativeWindow], clock: FakeClock  # noqa: F811
) -> None:
    made = open_light()
    session = made.session
    # Monday afternoon, before the block the test places at 16:00, so the whole week is still ahead.
    monday = datetime.fromisoformat(session.week_start)
    clock.set(monday + timedelta(hours=15))
    session.add_homework(essay(session))
    place_on_monday(qapp, session)
    assert session.start_focus(session.blocks[0]["id"], 0) is True
    session.add_homework({**session.assignments["essay"], "notes": "Cite two sources"})
    # The save's answer is held back while the 30 minutes of focus finish and are credited.
    session.client.hold()
    session.save()
    assert session.busy
    clock.move(minutes=30)
    session.tick_focus()
    session.client.release()
    settled(qapp, made)
    session.reload()
    settled(qapp, made)
    item = session.assignments["essay"]
    assert item["focus_minutes"] == 30
    assert item["notes"] == "Cite two sources"
