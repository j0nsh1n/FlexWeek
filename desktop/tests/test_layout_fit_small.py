"""The smallest window the app is meant for, 1024 x 640, at Large text: Clay's card in front stays whole
on the screen and the window keeps its size."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

    from desktop.native.layouts.clay import slots
    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import sanitize_look
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-fit-small-test"])
    yield application


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


@pytest.fixture()
def window(qapp: QApplication, tmp_path: Path) -> Iterator[NativeWindow]:
    """Signed in on the week page with setup skipped, as the other window tests start."""
    server = LocalServer(tmp_path / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    try:
        made.username.setText("fit_student")
        made.password.setText(PASSWORD)
        made.findChild(QPushButton, "createAccount").click()
        wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
        made.recovery_ack.setChecked(True)
        made.recovery_continue.click()
        past_setup(qapp, made)
        wait_until(qapp, lambda: made.session.preferences is not None)
        yield made
    finally:
        with contextlib.suppress(RuntimeError):
            made.session.client.reset()
        made.hide()
        qapp.processEvents()
        server.stop()


def clay_at_1024_by_640_large(qapp: QApplication, window: NativeWindow) -> None:
    """Clay on the week page, Large text, the window at the smallest size the app is meant for, with
    homework left over from last week so the planning strip above the deck takes its room, as it does
    for a student with work behind."""
    session = window.session
    monday = datetime.fromisoformat(session.week_start)
    due = (monday - timedelta(days=3)).strftime("%Y-%m-%dT23:59")
    session.add_homework({"id": "left", "title": "Lab report", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._carry_look()
    window._layout = sanitize_layout({"main": "clay", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.resize(1024, 640)
    window.show()
    for _ in range(20):
        qapp.processEvents()
    assert window.unfinished_panel.isVisibleTo(window), "the planning strip above the deck is not up"


def test_clays_front_card_is_whole_on_screen_at_1024_by_640_large_text(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The card in front is the deck's one thing to read. Mutation that turns this red: the row asks
    for 340 pixels of height at any text size (the old LEAST), so the page scrolls and the card's
    bottom is cut by the page's viewport."""
    clay_at_1024_by_640_large(qapp, window)
    page = window.findChild(QScrollArea, "clayScroll")
    assert page is not None and page.isVisible()
    row = window.planner.currentWidget().row
    card = slots(row.width(), row.height(), row.front, row.scale, wide=row._open)[row.front]
    top_left = row.mapTo(page.viewport(), card.toRect().topLeft())
    bottom = row.mapTo(page.viewport(), card.toRect().bottomLeft()).y()
    assert top_left.y() >= 0, "the card's top is above the page's viewport"
    assert bottom <= page.viewport().height(), (bottom, page.viewport().height())


def test_clay_at_1024_by_640_large_text_keeps_the_window_at_1024_by_640(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Passes before and after the row's minimum changed: the window stays put in this account. It
    guards against a Clay change that makes the window grow past the smallest size."""
    clay_at_1024_by_640_large(qapp, window)
    assert (window.width(), window.height()) == (1024, 640)
