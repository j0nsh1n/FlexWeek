"""Regression for item 1's "This week only / This week and later" prompt (fix-specs.md batch 12, item 1,
acceptance check 4): removing a standing (Setup) block from a week asks which; "This week only" leaves the
later weeks alone and survives reloading; "This week and later" takes it out of the standing week.

Window level: the editor's single ConfirmSheet, answered by clicking its button.
Known failures are xfail(strict=True).
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from desktop.native.widgets import BlockDialog
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

    tries = [0]

    def reply() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is None or sheet is dialog:
            # The sheet is built after the editor; look again until it is up, for a few seconds at most.
            tries[0] += 1
            if tries[0] < 100:
                QTimer.singleShot(50, reply)
            return
        buttons = [b for b in sheet.findChildren(QPushButton) if b.isVisible()]
        asked.extend(b.text() for b in buttons)
        question = sheet.findChild(QLabel, "confirmQuestion")
        if question is not None:
            asked.append(question.text())
        chosen = next((b for b in buttons if b.text() == answer), None)
        if chosen is not None:
            QTest.mouseClick(chosen, Qt.MouseButton.LeftButton)
        else:
            sheet.reject()

    QTimer.singleShot(200, reply)
    soccer = next(b for b in window.session.blocks if b["id"] == "activity-1")
    dialog = BlockDialog(window, soccer)
    # Delete is pressed in the editor on screen, so its question is drawn over it.
    dialog.show()
    dialog._delete()
    if dialog.deleted():
        window._delete_block(
            dialog.block(), dialog.scope(), dialog.occurrence_day(), every_week=dialog.delete_every_week()
        )
    wait_until(qapp, lambda: not window.session.busy and not window.session.dirty)
    settled(qapp, window)
    return asked


def test_1_removing_a_setup_block_asks_which_week_scope(qapp, window) -> None:
    set_up(qapp, window)
    asked = remove_soccer(qapp, window, "Cancel")
    assert {"This week only", "This week and later", "Cancel"} <= set(asked), asked
    assert "Delete Soccer on every Tue and Thu this week? Earlier weeks keep it." in asked
    assert shown_days(window.session, "activity-1") == [1, 3], "Cancel removed it"


def test_1_this_week_only_keeps_soccer_in_the_week_after_and_survives_reloading(qapp, window) -> None:
    home = set_up(qapp, window)
    session = window.session
    remove_soccer(qapp, window, "This week only")
    assert shown_days(session, "activity-1") == []
    go_to(qapp, session, plus_weeks(home, 2))
    assert shown_days(session, "activity-1") == [1, 3]
    go_to(qapp, session, plus_weeks(home, 1))  # back, read from the store again
    assert shown_days(session, "activity-1") == []
    assert shown_days(session, "school") == [0, 1, 2, 3, 4]


def test_1_this_week_and_later_takes_soccer_out_of_this_and_every_later_week_only(qapp, window) -> None:
    home = set_up(qapp, window)
    session = window.session
    remove_soccer(qapp, window, "This week and later")
    seen = {}
    for weeks in (1, 2, 4, 0):
        go_to(qapp, session, plus_weeks(home, weeks))
        seen[weeks] = shown_days(session, "activity-1")
    assert seen == {1: [], 2: [], 4: [], 0: [1, 3]}, seen
