"""The overdue card above the week at 1024 x 640, Large text: its two buttons show their whole labels.
With room they share the line with the words; without, they move under the words."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import time
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPoint, QRect, QStandardPaths
    from PySide6.QtWidgets import QApplication, QPushButton

    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.look import sanitize_look
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"
LONG_WORDS = "1 overdue · 3 left from last week"
DESIGNS = ("classic", "timeline", "mission", "bento", "retro", "clay")


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    application = QApplication.instance() or QApplication(["flexweek-overdue-card-test"])
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
    server = LocalServer(tmp_path / "flexweek.db")
    server.start()
    made = NativeWindow(server.origin)
    made.show()
    try:
        made.username.setText("overdue_student")
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


def overdue_card_at_1024_by_640_large(qapp: QApplication, window: NativeWindow, main: str) -> None:
    """One homework left overdue, the planning panel folded so the card shows, Large text, 1024 by 640."""
    session = window.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {"id": "bio", "title": "Bio reading", "due": (monday + timedelta(days=4)).isoformat() + "T23:59",
         "estimate_min": 60, "revision": 0}
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    assert session.place_session(block["id"], 2, 15 * 60 + 15)
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=5, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    session.look = window._look
    window._carry_look()
    window._layout = sanitize_layout({"main": main, "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.resize(1024, 640)
    window.show()
    window.unfinished_panel._collapse()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    for _ in range(30):
        qapp.processEvents()
    assert window.left_chip.isVisible(), "the overdue card is not showing"


def buttons_of(window: NativeWindow) -> tuple[QPushButton, QPushButton]:
    return window.findChild(QPushButton, "leftPlan"), window.findChild(QPushButton, "leftDone")


@pytest.mark.parametrize("main", DESIGNS)
def test_the_overdue_buttons_show_their_whole_labels_at_1024_by_640_large_with_long_words(
    qapp: QApplication, window: NativeWindow, main: str
) -> None:
    """Mutation that turns this red: _fit_left_chip returns before it moves anything. The line then
    squeezes both buttons to fit the long words beside them."""
    overdue_card_at_1024_by_640_large(qapp, window, main)
    window.left_chip_text.setText(LONG_WORDS)
    window._fit_left_chip()
    for _ in range(20):
        qapp.processEvents()
    card = QRect(window.left_chip.mapTo(window, QPoint(0, 0)), window.left_chip.size())
    for button in buttons_of(window):
        assert button.width() >= button.sizeHint().width(), (main, button.text(), button.width())
        assert button.isVisible()
        assert card.contains(QRect(button.mapTo(window, QPoint(0, 0)), button.size())), (main, button.text())


def test_long_words_move_the_buttons_under_them_when_the_card_has_no_room_beside(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The rail sits beside the week in Classic, so the card is 746 pixels wide here. With the long
    words the buttons go on a row under the words, lined up under them."""
    overdue_card_at_1024_by_640_large(qapp, window, "classic")
    window.left_chip_text.setText(LONG_WORDS)
    window._fit_left_chip()
    for _ in range(20):
        qapp.processEvents()
    plan, done = buttons_of(window)
    words = window.left_chip_text
    assert plan.mapTo(window, plan.rect().topLeft()).y() > words.mapTo(window, words.rect().bottomLeft()).y()
    assert plan.mapTo(window, plan.rect().topLeft()).x() >= words.mapTo(window, words.rect().topLeft()).x()
    assert done.mapTo(window, done.rect().topLeft()).x() > plan.mapTo(window, plan.rect().topLeft()).x()


def test_short_words_keep_the_buttons_on_the_words_line(qapp: QApplication, window: NativeWindow) -> None:
    """With room for the words and both buttons whole, nothing moves: the buttons share the words' line."""
    overdue_card_at_1024_by_640_large(qapp, window, "classic")
    plan, done = buttons_of(window)
    words = window.left_chip_text
    line_top = words.mapTo(window, words.rect().topLeft()).y()
    for button in (plan, done):
        assert button.mapTo(window, button.rect().topLeft()).y() <= line_top + words.height()
        assert not window._chip_below.isVisible()
