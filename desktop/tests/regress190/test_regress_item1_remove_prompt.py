"""Regression for item 1's "Just this week / Every week" prompt (fix-specs.md batch 12, item 1, acceptance
check 4): removing a standing (Setup) block from a week asks which; "Just this week" leaves the later weeks
alone and survives reloading; "Every week" takes it out of the standing week.

Window level: the real `_delete_block` path and its ConfirmSheet, answered by clicking its button.
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)
from desktop.tests.regress184.test_regress_item1_next_week_school import SCHOOL, SOCCER, go_to, plus_weeks


def shown_days(session, ident: str) -> list[int]:
    for block in session.blocks:
        if block["id"] == ident:
            return sorted(set(block.get("days") or []) - set(block.get("missed_days") or []))
    return []


def set_up(qapp, window) -> str:
    session = window.session
    session.set_setup_blocks([dict(SCHOOL), dict(SOCCER)])
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled(qapp, window)
    home = session.week_start
    go_to(qapp, session, plus_weeks(home, 1))
    assert shown_days(session, "activity-1") == [1, 3]
    return home


def remove_soccer(qapp, window, answer: str) -> list[str]:
    asked: list[str] = []

    def reply() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is None:
            return
        buttons = [b for b in sheet.findChildren(QPushButton) if b.isVisible()]
        asked.extend(b.text() for b in buttons)
        chosen = next((b for b in buttons if b.text() == answer), None)
        if chosen is not None:
            QTest.mouseClick(chosen, Qt.MouseButton.LeftButton)
        else:
            sheet.reject()

    QTimer.singleShot(200, reply)
    soccer = next(b for b in window.session.blocks if b["id"] == "activity-1")
    window._delete_block(soccer, "series", None)
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    settled(qapp, window)
    return asked


def test_1_removing_a_setup_block_asks_just_this_week_or_every_week(qapp, window) -> None:
    set_up(qapp, window)
    asked = remove_soccer(qapp, window, "Cancel")
    assert {"Just this week", "Every week", "Cancel"} <= set(asked), asked
    assert shown_days(window.session, "activity-1") == [1, 3], "Cancel removed it"


def test_1_just_this_week_keeps_soccer_in_the_week_after_and_survives_reloading(qapp, window) -> None:
    home = set_up(qapp, window)
    session = window.session
    remove_soccer(qapp, window, "Just this week")
    assert shown_days(session, "activity-1") == []
    go_to(qapp, session, plus_weeks(home, 2))
    assert shown_days(session, "activity-1") == [1, 3]
    go_to(qapp, session, plus_weeks(home, 1))  # back, read from the store again
    assert shown_days(session, "activity-1") == []
    assert shown_days(session, "school") == [0, 1, 2, 3, 4]


def test_1_every_week_takes_soccer_out_of_this_and_every_later_week_only(qapp, window) -> None:
    home = set_up(qapp, window)
    session = window.session
    remove_soccer(qapp, window, "Every week")
    seen = {}
    for weeks in (1, 2, 4, 0):
        go_to(qapp, session, plus_weeks(home, weeks))
        seen[weeks] = shown_days(session, "activity-1")
    assert seen == {1: [], 2: [], 4: [], 0: [1, 3]}, seen
