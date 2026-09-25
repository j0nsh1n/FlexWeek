"""Homework and planning through the real window: new homework is due today, changing the due date
runs what hangs off it, Plan never puts anything before now, a homework's length is checked in words
beside its box, the due date's calendar shows its whole month, and one Plan is one Undo.
"""

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
    from PySide6.QtCore import QDate, QStandardPaths, Qt, QTime
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QPushButton,
        QWidget,
    )

    from desktop.native.calendar import date_for_day, sunday_due
    from desktop.native.widgets import DueField, HomeworkDialog
    from desktop.native.window import NativeWindow
    from desktop.server import LocalServer
    from desktop.tests.logic_support import past_setup

PASSWORD = "a-long-test-password"
TOO_LATE = "There is not enough time left before it is due, even with nothing else planned."
PAST_WEEK = "This week is over, so nothing was planned. Plan this week or a later one."


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-homework-plan-test"])


def wait_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was still false")


def settled(qapp: QApplication, window: NativeWindow) -> None:
    for _ in range(3):
        wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
        QTest.qWait(40)


def look_file() -> Path:
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "flexweek-look.json"


def signed_up(qapp: QApplication, server: LocalServer, name: str) -> NativeWindow:
    made = NativeWindow(server.origin)
    made.resize(1280, 860)
    made.show()
    made.username.setText(name)
    made.password.setText(PASSWORD)
    made.findChild(QPushButton, "createAccount").click()
    wait_until(qapp, lambda: made._stack.currentWidget().objectName() == "recoveryPage")
    made.recovery_ack.setChecked(True)
    made.recovery_continue.click()
    return made


def closed(qapp: QApplication, made: NativeWindow) -> None:
    with contextlib.suppress(RuntimeError):
        made.session.client.reset()
    made.hide()
    qapp.processEvents()


@pytest.fixture()
def server(qapp: QApplication, tmp_path: Path) -> Iterator[LocalServer]:
    look_file().unlink(missing_ok=True)
    running = LocalServer(tmp_path / "flexweek.db")
    running.start()
    yield running
    running.stop()
    look_file().unlink(missing_ok=True)


@pytest.fixture()
def window(qapp: QApplication, server: LocalServer) -> Iterator[NativeWindow]:
    """This week: School Monday to Friday 08:00-14:30, the History essay placed by hand on Thursday
    19:00-20:00, and a Math worksheet due Sunday that still needs a time. The clock is held at
    Thursday 10:00."""
    made = signed_up(qapp, server, "plan_student")
    try:
        past_setup(qapp, made)
        session = made.session
        thursday = datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=10)
        session.now_ms = lambda: int(thursday.timestamp() * 1000)
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
        due = sunday_due(session.week_start)
        for key, title in (("essay", "History essay"), ("math", "Math worksheet")):
            session.add_homework({"id": key, "title": title, "due": due, "estimate_min": 60, "revision": 0})
        session.save()
        settled(qapp, made)
        session.place_session(session_of(made, "essay")["id"], 3, 19 * 60)
        session.save()
        settled(qapp, made)
        yield made
    finally:
        closed(qapp, made)


def session_of(window: NativeWindow, assignment_id: str) -> dict:
    return next(block for block in window.session.blocks if block.get("assignment_id") == assignment_id)


def thursday_iso(window: NativeWindow) -> str:
    return date_for_day(window.session.week_start, 3)


def opened_with(
    monkeypatch: pytest.MonkeyPatch, act: Callable[[HomeworkDialog], int]
) -> list[HomeworkDialog]:
    """Every homework editor the window opens is handed to `act` instead of waiting for a student."""
    seen: list[HomeworkDialog] = []

    def run(dialog: HomeworkDialog) -> int:
        seen.append(dialog)
        return act(dialog)

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    return seen


def press(dialog: QDialog, name: str) -> int:
    dialog.findChild(QPushButton, name).click()
    return QDialog.DialogCode.Accepted


# Due today


def test_new_homework_opens_due_today_whatever_week_is_on_screen(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    dues: list[str] = []

    def look(dialog: HomeworkDialog) -> int:
        dues.append(dialog.due.value())
        return QDialog.DialogCode.Rejected

    opened_with(monkeypatch, look)
    window._add_homework()
    today = thursday_iso(window)
    assert dues == [today], "due today, not on the Monday of the week on screen"

    dues.clear()
    window._edit_homework("math")
    assert dues == [window.session.assignments["math"]["due"][:10]], "editing keeps its own due date"

    ahead = (date.fromisoformat(window.session.week_start) + timedelta(days=7)).isoformat()
    window.session.load_week(ahead)
    wait_until(qapp, lambda: window.session.week_start == ahead and not window.session.busy)
    window._add_homework()
    assert dues[-1] == today


# The due date's follow-ups


def test_changing_the_due_date_turns_off_what_acts_on_the_saved_homework(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spread and Let FlexWeek move it act on the saved homework, so an unsaved edit turns them off.
    The due date's signal handed a date to a signal that takes none, raised inside Qt, and nothing
    connected after it ran."""
    states: list[tuple[str, bool, bool]] = []

    def change(dialog: HomeworkDialog) -> int:
        spread = dialog.findChild(QPushButton, "spreadHomework")
        unpin = dialog.findChild(QPushButton, "homeworkUnpin")
        states.append(("opened", spread.isEnabled(), unpin.isEnabled()))
        dialog.due.date.setDate(dialog.due.date.date().addDays(-1))
        states.append(("date", spread.isEnabled(), unpin.isEnabled()))
        return QDialog.DialogCode.Rejected

    opened_with(monkeypatch, change)
    window._edit_homework("essay")
    assert states == [("opened", True, True), ("date", False, False)]

    for step in ("timed", "time"):
        states.clear()

        def other(dialog: HomeworkDialog, step: str = step) -> int:
            spread = dialog.findChild(QPushButton, "spreadHomework")
            if step == "timed":
                dialog.due.timed.setChecked(True)
            else:
                dialog.due.time.setTime(QTime(7, 45))
            states.append((step, spread.isEnabled(), True))
            return QDialog.DialogCode.Rejected

        opened_with(monkeypatch, other)
        window._edit_homework("essay")
        assert states == [(step, False, True)], f"changing the {step} turns Spread off too"


def test_a_due_field_says_it_changed_with_no_arguments(qapp: QApplication) -> None:
    field = DueField("2026-09-24", "probe")
    heard: list[tuple] = []
    field.changed.connect(lambda *args: heard.append(args))
    field.date.setDate(QDate(2026, 9, 25))
    field.timed.setChecked(True)
    field.time.setTime(QTime(8, 15))
    assert heard == [(), (), ()]


# Length


def typed(box: QWidget, text: str) -> None:
    box.setFocus()
    box.selectAll()
    QTest.keyClicks(box, text)


def test_a_length_under_15_minutes_or_over_24_hours_is_refused_beside_the_box(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    said: list[tuple[str, int, bool, bool]] = []

    def enter(dialog: HomeworkDialog) -> int:
        dialog.show()
        dialog.title.setText("Science poster")
        hint = dialog.estimate_hint

        def saved_as(text: str) -> None:
            typed(dialog.estimate, text)
            dialog.accept()
            problem = bool(hint.property("problem"))
            said.append((hint.text(), dialog.estimate.value(), problem, dialog.isVisible()))

        saved_as("0")
        saved_as("1500")
        typed(dialog.estimate, "1440")
        QTest.keyClick(dialog.estimate, Qt.Key.Key_Up)
        said.append(("cap", dialog.estimate.value(), False, False))
        saved_as("90")
        return dialog.result()

    opened_with(monkeypatch, enter)
    window._add_homework()
    settled(qapp, window)
    zero, long, cap, fine = said
    assert zero == ("Give it at least 15 minutes.", 0, True, True), "0 is kept as typed and refused in words"
    assert long[1:] == (1500, True, True) and "Split it into parts" in long[0]
    assert cap[1] == 1440, "the arrows stop at 24 hours"
    assert fine[2:] == (False, False), "a length in range saves"
    saved = next(item for item in window.session.assignments.values() if item["title"] == "Science poster")
    assert saved["estimate_min"] == 90
