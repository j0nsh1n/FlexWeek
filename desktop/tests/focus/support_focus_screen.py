"""What the focus tests share: a light Week with the History essay on now, Material on screen with
homework to focus on, and answering the sheet that Finish asks."""

# ruff: noqa: F811  (pytest fixtures defined here are used by name)
from __future__ import annotations

import contextlib
import itertools
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QPushButton

from backend.tests.fake_clock import CLOCK
from desktop.native.calendar import sunday_due
from desktop.native.widgets import ConfirmSheet
from desktop.native.window import NativeWindow
from desktop.tests.light_app import LightWindows
from desktop.tests.waiting import wait_until

LEFT = Qt.MouseButton.LeftButton


def settled(qapp: QApplication, window: NativeWindow) -> None:
    """The window has nothing left to save and no reply on its way."""
    session = window.session
    wait_until(
        qapp,
        lambda: (
            not session.busy
            and not session.dirty
            and not any(session.client._replies.values())
            and not getattr(session.client, "pending", 0)
        ),
        what="the window finishing its saves",
    )


@pytest.fixture()
def focus_window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """Today's app's Week with the History essay on Thursday 19:00 and the clock held at Thursday
    19:10, so the essay is on now."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open((1280, 860))
        session = made.session
        CLOCK.set(datetime.fromisoformat(session.week_start) + timedelta(days=3, hours=19, minutes=10))
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
        settled(qapp, made)
        essay = next(block for block in session.blocks if block.get("assignment_id") == "essay")
        session.add_block({**essay, "start": "19:00", "days": [3], "pinned": True})
        session.save()
        settled(qapp, made)
        made.findChild(QAbstractButton, "viewWeek").click()
        settled(qapp, made)
        yield made
    finally:
        windows.close()


@pytest.fixture()
def material_focus_window(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory, tmp_path: Path
) -> Iterator[NativeWindow]:
    """A fresh light window for Material's focus tests, with no timer left running when it closes."""
    windows = LightWindows(qapp, tmp_path_factory.getbasetemp(), tmp_path)
    try:
        made = windows.open((1280, 800))
        try:
            yield made
        finally:
            with contextlib.suppress(RuntimeError):
                made.session.reset_focus()
    finally:
        windows.close()


@contextlib.contextmanager
def rules(window: NativeWindow, owned: bool = True, **prefs: object) -> Iterator[None]:
    """Material's focus rules on (or off) with these preferences, for one test."""
    session = window.session
    before = session.preferences
    before_owner = session.material_owns
    session.preferences = {**(before or {}), **prefs}
    session.material_owns = (lambda: True) if owned else None
    try:
        yield
    finally:
        session.reset_focus()
        session.preferences = before
        session.material_owns = before_owner


def on_screen(window: NativeWindow) -> str:
    return window._stack.currentWidget().objectName()


def visible_buttons(widget) -> list[str]:
    return [button.text() for button in widget.findChildren(QPushButton) if button.isVisible()]


def quick_focus(window: NativeWindow) -> None:
    """More > Quick focus, then Start: Quick focus opens the screen ready, as F does (decision 19)."""
    window.findChild(QPushButton, "quickFocusAction").click()
    assert window.session.focus is None, "Quick focus waits for Start"
    assert on_screen(window) == "focusPage"
    assert visible_buttons(window.focus_screen) == ["Back", "Start"]
    assert window.focus_screen.ring._waiting, "set but not started"
    QTest.mouseClick(window.focus_screen.start, LEFT)
    assert window.session.focus is not None
    assert not window.focus_screen.ring._waiting


def end_sheet_answer(monkeypatch: pytest.MonkeyPatch, window: NativeWindow, key: str) -> list[ConfirmSheet]:
    """Press Finish and answer the sheet it opens with `key`; the sheets seen are returned."""
    seen: list[ConfirmSheet] = []

    def run(sheet: ConfirmSheet) -> int:
        seen.append(sheet)
        sheet.buttons[key].click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ConfirmSheet, "exec", run)
    QTest.mouseClick(window.focus_screen.stop, LEFT)
    return seen


SLOT = itertools.count()


def next_slot() -> tuple[int, str]:
    """A free evening half hour on Monday to Friday, so no two blocks share one."""
    index = next(SLOT)
    return index // 16, f"{16 + (index % 16) // 2}:{'30' if index % 2 else '00'}"


def homework(qapp: QApplication, window: NativeWindow, name: str, sessions: int) -> list[dict]:
    """A homework with `sessions` placed work blocks, each 30 minutes."""
    session = window.session
    session.add_homework(
        {
            "id": name,
            "title": name.title(),
            "due": sunday_due(session.week_start),
            "estimate_min": 30 * sessions,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    first = next(block for block in session.blocks if block.get("assignment_id") == name)
    day, start = next_slot()
    first.update({"start": start, "days": [day], "duration_min": 30})
    session.add_block(first)
    for index in range(1, sessions):
        extra = deepcopy(first)
        day, start = next_slot()
        extra.update({"id": f"{name}-{index}", "start": start, "days": [day]})
        session.add_block(extra)
    session.save()
    settled(qapp, window)
    return [block for block in session.blocks if block.get("assignment_id") == name]


def run_out(qapp: QApplication, window: NativeWindow) -> None:
    """The countdown reaches zero."""
    session = window.session
    session.focus["endsAt"] = session.now_ms() - 1
    session.tick_focus()
    settled(qapp, window)


def start(window: NativeWindow, block: dict) -> bool:
    return window.session.start_focus(block["id"], block["days"][0])


def block_named(window: NativeWindow, block_id: str) -> dict:
    return next(block for block in window.session.blocks if block["id"] == block_id)

