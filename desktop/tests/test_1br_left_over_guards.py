"""Guards for 1b-R beyond Regression Tester's suite: the More badge opens the shared left-over rows, the
deadline timer refreshes tags, sidebar and focus list, and the week list names the due date.

Same held-clock scenarios as desktop/tests/regress190/test_regress_qa0190_1br_left_over.py: Bio reading
placed Wednesday 3:15 PM of the open week, due Friday 23:59, not ticked, clock Saturday 10:00.
"""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from desktop.native.client import ApiError
from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.weekmodel import length_label, range_label
from desktop.tests.blocks_helper import put_block
from desktop.tests.grid_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_in,
    signed_out,
    wait_until,
    window,
)
from desktop.tests.regress184.test_regress_item1b_unfinished_past_week import left_in_week_one

WEDNESDAY, FRIDAY, SATURDAY = 2, 4, 5
SMALL_WINDOW = (1024, 640)
NORMAL_WINDOW = (1280, 800)
LINE_CENTER_TOLERANCE = 4
EVENT_PASSES = 20


def overdue_this_week(qapp, window) -> str:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(b for b in session.blocks if b.get("assignment_id") == "bio")
    put_block(session, block["id"], WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15, pinned=True)
    session.save()
    settled(qapp, window)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    return block["id"]


def open_unfinished_at(qapp, window, width: int, height: int, text: str) -> None:
    """Classic week, the unfinished list open, at this window size and text size."""
    window._look = sanitize_look({"preset": "default", "knobs": {"text": text}})
    window.session.look = window._look
    window._carry_look()
    window._layout = sanitize_layout({"main": "classic", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.resize(width, height)
    window.show()
    window._show_unfinished()
    settled(qapp, window)
    for _ in range(EVENT_PASSES):
        qapp.processEvents()


def unfinished_row_buttons(window):
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    return row, [
        button
        for button in row.findChildren(QPushButton)
        if button.objectName().split("-")[0] in {"focusUnfinished", "planUnfinished", "deleteUnfinished"}
    ]


def test_1br_chip_and_planning_box_say_plan_into_this_week_and_mark_as_finished(qapp, window) -> None:
    overdue_this_week(qapp, window)
    assert window.findChild(QPushButton, "leftPlan").text() == "Plan into this week"
    assert window.findChild(QPushButton, "leftDone").text() == "Mark as finished"
    asked: list[list[str]] = []

    def look() -> None:
        sheet = QApplication.activeModalWidget()
        if sheet is not None:
            asked.append([b.text() for b in sheet.findChildren(QPushButton)])
            sheet.reject()

    QTimer.singleShot(300, look)
    window.findChild(QPushButton, "solveButton").click()
    for _ in range(12):
        QTest.qWait(50)
    settled(qapp, window)
    assert asked and "Plan into this week" in asked[0] and "Mark as finished" in asked[0], asked
    assert "I did these" not in asked[0] and "Plan them" not in asked[0], asked


def test_1br_the_week_list_row_says_overdue_with_the_due_date(qapp, window) -> None:
    overdue_this_week(qapp, window)
    listing = window.week_access_list
    rows = [
        listing.item(i).text()
        for i in range(listing.count())
        if listing.item(i).text().startswith("Wednesday: Bio reading, ")
    ]
    due = date.fromisoformat(window.session.assignments["bio"]["due"][:10])
    due_words = f"Overdue, was due {due.strftime('%a')} {due.day} {due.strftime('%b')}"
    times = range_label(15 * 60 + 15, 16 * 60 + 15)
    expected = f"Wednesday: Bio reading, {times} · {length_label(60)} · {due_words} · Pinned"
    assert rows == [expected]


def test_1br_more_badge_opens_the_shared_left_over_rows(qapp, window) -> None:
    left_in_week_one(qapp, window)
    window.unfinished_panel._collapse()
    window.findChild(QPushButton, "unfinishedOpen").click()
    settled(qapp, window)
    assert window.unfinished_panel.isVisible()
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    due = date.fromisoformat(window.session.assignments["lab"]["due"][:10])
    words = (
        f"Lab report · 1 h left · due {due.strftime('%a')} {due.day} {due.strftime('%b')} "
        "· Left from last week"
    )
    assert row.accessibleName() == words
    assert row.findChild(QLabel, "unfinishedRow").text() == words
    focus = row.findChild(QPushButton, "focusUnfinished-lab")
    assert focus is not None and focus.text() == "Start focus"
    assert focus.accessibleName() == "Start focus on Lab report"


def test_1br_unfinished_row_buttons_stay_whole_at_1024_by_640_large(qapp, window) -> None:
    """Mutation that turns this red: _fit_row returns before it moves the buttons under the words.
    Find a time and Delete then sit past the panel's right edge at 1024 x 640 Large text."""
    overdue_this_week(qapp, window)
    open_unfinished_at(qapp, window, *SMALL_WINDOW, "large")
    panel = window.unfinished_panel
    assert panel.isVisibleTo(window)
    row, buttons = unfinished_row_buttons(window)
    assert buttons, "the unfinished row has its action buttons"
    panel_rect = QRect(panel.mapTo(window, QPoint(0, 0)), panel.size())
    list_rect = QRect(panel.list.viewport().mapTo(window, QPoint(0, 0)), panel.list.viewport().size())
    for button in buttons:
        assert button.isVisibleTo(panel), button.text()
        assert button.width() >= button.sizeHint().width(), (button.text(), button.width())
        placed = QRect(button.mapTo(window, QPoint(0, 0)), button.size())
        assert panel_rect.contains(placed), (button.text(), placed, panel_rect)
        assert list_rect.contains(placed), (button.text(), placed, list_rect)
        assert row.rect().contains(QRect(button.mapTo(row, QPoint(0, 0)), button.size())), button.text()
    text = row.findChild(QLabel, "unfinishedRow")
    assert text is not None
    words = QFontMetrics(text.font()).horizontalAdvance(text.text())
    assert text.width() >= words or (
        text.wordWrap() and text.height() >= text.heightForWidth(text.width())
    ), (text.text(), text.width(), words)
    words_bottom = text.mapTo(row, text.rect().bottomLeft()).y()
    for button in buttons:
        assert button.mapTo(row, button.rect().topLeft()).y() >= words_bottom, button.text()
    assert panel.list.horizontalScrollBar().maximum() == 0


def test_1br_several_wrapped_unfinished_rows_leave_room_for_hide_at_640(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    for key, title in (("chemistry", "Long chemistry report"), ("history", "Long history essay")):
        session.add_homework(
            {
                "id": key,
                "title": title,
                "due": session.assignments["bio"]["due"],
                "estimate_min": 1440,
                "revision": 0,
                "spread": "one",
            }
        )
    session.save()
    settled(qapp, window)
    open_unfinished_at(qapp, window, *SMALL_WINDOW, "large")
    assert (window.width(), window.height()) == SMALL_WINDOW
    panel = window.unfinished_panel
    assert panel.list.count() == 3
    dismiss = panel.findChild(QPushButton, "unfinishedDismiss")
    placed = QRect(dismiss.mapTo(window, QPoint(0, 0)), dismiss.size())
    assert window.rect().contains(placed)
    assert panel.list.verticalScrollBar().maximum() > 0


def test_1br_unfinished_row_buttons_share_the_text_line_at_1280_normal(qapp, window) -> None:
    overdue_this_week(qapp, window)
    open_unfinished_at(qapp, window, *NORMAL_WINDOW, "normal")
    row, buttons = unfinished_row_buttons(window)
    text = row.findChild(QLabel, "unfinishedRow")
    below = row.findChild(QWidget, "unfinishedRowBelow")
    assert text is not None and buttons
    for button in buttons:
        assert abs(button.geometry().center().y() - text.geometry().center().y()) <= LINE_CENTER_TOLERANCE, (
            button.text()
        )
    assert below is None or not below.isVisible()


def test_1br_overdue_chip_hides_with_unfinished_and_returns_when_hidden(qapp, window) -> None:
    overdue_this_week(qapp, window)
    monday = date.fromisoformat(window.session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    window.session.add_homework(
        {"id": "chem", "title": "Chem lab", "due": due, "estimate_min": 60, "revision": 0}
    )
    window.session.save()
    settled(qapp, window)
    window._on_week()
    settled(qapp, window)
    if window.unfinished_panel.isVisibleTo(window):
        window.unfinished_panel.findChild(QPushButton, "unfinishedDismiss").click()
        settled(qapp, window)
    assert window.left_chip.isVisibleTo(window)

    window.findChild(QPushButton, "unfinishedOpen").click()
    settled(qapp, window)
    assert window.unfinished_panel.isVisibleTo(window)
    assert not window.left_chip.isVisibleTo(window)
    window.session.week_changed.emit()
    settled(qapp, window)
    assert not window.left_chip.isVisibleTo(window)

    window.unfinished_panel.findChild(QPushButton, "unfinishedDismiss").click()
    settled(qapp, window)
    assert not window.unfinished_panel.isVisibleTo(window)
    assert window.left_chip.isVisibleTo(window)


def test_1br_deadline_timer_refreshes_tags_sidebar_and_focus(qapp, window, monkeypatch) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    friday = monday + timedelta(days=FRIDAY)
    due = friday.isoformat() + "T23:59"
    session.add_homework({"id": "bio", "title": "Bio reading", "due": due, "estimate_min": 60, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "bio")
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60 + 15, 16 * 60 + 15)
    session.save()
    settled(qapp, window)
    announcements = []
    monkeypatch.setattr(
        "desktop.native.window.announce",
        lambda widget, words, assertive=False: announcements.append((widget, words, assertive)),
    )
    before = datetime.combine(friday, datetime.min.time()).replace(hour=23, minute=58)
    after = before + timedelta(minutes=3)
    session.now_ms = lambda: int(before.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    assert not session.unfinished()
    assert 0 < window._deadline_tick.remainingTime() <= 61_000
    session.now_ms = lambda: int(after.timestamp() * 1000)
    window._deadline_tick.timeout.emit()
    settled(qapp, window)
    assert session.unfinished()[0]["left_over_state"] == "overdue"
    rows = [window.week_access_list.item(i).text() for i in range(window.week_access_list.count())]
    due = friday
    due_words = f"Overdue, was due {due.strftime('%a')} {due.day} {due.strftime('%b')}"
    times = range_label(15 * 60 + 15, 16 * 60 + 15)
    expected = f"Wednesday: Bio reading, {times} · {length_label(60)} · {due_words} · Pinned"
    bio_rows = [row for row in rows if row.startswith("Wednesday: Bio reading, ")]
    assert bio_rows == [expected]
    leftover_words = "Everything has a time."
    overdue_words = "1 overdue"
    assert window.rail.none_waiting.text() == leftover_words
    assert any(item["title"] == "Bio reading, overdue" for item in session.focus_tasks())
    unfinished = window.findChild(QPushButton, "unfinishedOpen")
    said = [item for item in announcements if item[0] is unfinished]
    assert said == [(unfinished, overdue_words, False)]
    window._deadline_changed()
    settled(qapp, window)
    assert [item for item in announcements if item[0] is unfinished] == said


def test_1br_the_overdue_focus_row_starts_from_the_homework(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    row = next(item for item in window.session.focus_tasks() if item["title"] == "Bio reading, overdue")
    assert row["id"] == "bio" and row["id"] != session_id
    assert window.session.start_focus(row["id"], row["day"]) is True
    focus = window.session.focus
    assert focus["title"] == "Bio reading, overdue"
    assert focus["assignmentId"] == "bio" and focus["blockId"] is None


def test_1br_panel_focus_restores_and_credits_homework(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    session.preferences["timer_work_min"] = 25
    window._show_unfinished()
    settled(qapp, window)
    assert window.unfinished_panel.isVisibleTo(window)
    row = window.unfinished_panel.list.itemWidget(window.unfinished_panel.list.item(0))
    button = row.findChild(QPushButton, "focusUnfinished-bio")
    assert button is not None
    assert button.accessibleName() == "Start focus on Bio reading"
    button.click()
    assert session.focus["assignmentId"] == "bio"
    session._reset_focus(persist=False)
    session._restore_focus()
    assert session.focus["title"] == "Bio reading"
    session.advance_focus(completed=True)
    settled(qapp, window)
    session.reload()
    settled(qapp, window)
    assert session.assignments["bio"]["focus_minutes"] == 25
    assert session.assignments["bio"]["focus_sessions"] == 1
    assert session.assignments["bio"]["completed"] is False


def test_1br_next_week_does_not_call_current_week_work_carried(qapp, window) -> None:
    session = window.session
    week = session.week_start
    monday = date.fromisoformat(week)
    session.now_ms = lambda: int(datetime.combine(monday, datetime.min.time()).timestamp() * 1000)
    earlier = (monday - timedelta(days=7)).isoformat()
    session.load_week(earlier)
    settled(qapp, window)
    session.add_block({"id": "old", "title": "Old class", "kind": "locked", "days": [0],
                       "start": "08:00", "duration_min": 60})
    session.save()
    settled(qapp, window)
    session.load_week(week)
    settled(qapp, window)
    session.add_homework({"id": "future", "title": "Future", "estimate_min": 60,
                          "due": (monday + timedelta(days=6)).isoformat() + "T23:59", "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "future")
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60, 15 * 60 + block["duration_min"])
    session.save()
    settled(qapp, window)
    session.load_week((monday + timedelta(days=7)).isoformat())
    settled(qapp, window)
    assert session.assignments["future"]["unplanned_min"] == 60
    assert session.unfinished() == []


def test_1br_plan_overdue_reuses_the_session_and_keeps_other_blocks(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "14:00"}]})
    settled(qapp, window)
    session.add_block({"id": "class", "title": "Class", "kind": "locked", "days": [SATURDAY],
                       "start": "10:00", "duration_min": 60})
    session.save()
    settled(qapp, window)
    before_class = next(item.copy() for item in session.blocks if item["id"] == "class")
    due = session.assignments["bio"]["due"]
    session.plan_left(["bio"])
    settled(qapp, window)
    bio = [item for item in session.blocks if item.get("assignment_id") == "bio"]
    assert len(bio) == 1
    assert (bio[0]["id"], bio[0]["days"], bio[0]["start"]) == (session_id, [SATURDAY], "11:00")
    assert session.message == "Placed 1 homework block."
    assert session.assignments["bio"]["due"] == due
    assert next(item for item in session.blocks if item["id"] == "class") == before_class
    session.plan_left(["bio"])
    settled(qapp, window)
    assert len([item for item in session.blocks if item.get("assignment_id") == "bio"]) == 1
    session.add_block({"id": "lunch", "title": "Lunch", "kind": "locked", "days": [SATURDAY],
                       "start": "13:00", "duration_min": 30})
    session.save()
    settled(qapp, window)
    session.reload()
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    assert (bio["days"], bio["start"]) == ([SATURDAY], "11:00")
    session.add_homework({**session.assignments["bio"], "title": "Biology reading"})
    session.save()
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    assert (bio["title"], bio["days"], bio["start"]) == ("Biology reading", [SATURDAY], "11:00")


def test_1br_overdue_plan_with_no_room_does_not_add_an_unplaced_block(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "11:00"}]})
    settled(qapp, window)
    session.add_block({"id": "class", "title": "Class", "kind": "locked", "days": [SATURDAY],
                       "start": "10:00", "duration_min": 60})
    session.save()
    settled(qapp, window)
    before = [item.copy() for item in session.blocks]
    session.plan_left(["bio"])
    settled(qapp, window)
    assert session.blocks == before
    assert session.message == "Nothing placed."
    session.reload()
    settled(qapp, window)
    assert session.blocks == before


def test_1br_selected_overdue_plan_leaves_other_homework_alone(qapp, window) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=6)).isoformat() + "T23:59"
    for key in ("other", "waiting"):
        session.add_homework({"id": key, "title": key.title(), "estimate_min": 60, "due": due,
                              "revision": 0})
    session.save()
    settled(qapp, window)
    other = next(item for item in session.blocks if item.get("assignment_id") == "other")
    waiting = next(item for item in session.blocks if item.get("assignment_id") == "waiting")
    assert session.hand_move(other["id"], -1, SATURDAY, 12 * 60, 13 * 60)
    session.delete_block(waiting["id"])
    session.save()
    settled(qapp, window)
    before_other = next(item.copy() for item in session.blocks if item["id"] == other["id"])
    before_ids = {item["id"] for item in session.blocks}
    session.plan_left(["bio"])
    settled(qapp, window)
    assert {item["id"] for item in session.blocks} == before_ids
    assert next(item for item in session.blocks if item["id"] == other["id"]) == before_other

    bio = next(item for item in session.blocks if item.get("assignment_id") == "bio")
    assert (bio["days"], bio["start"]) == ([SATURDAY], "10:00")
    session.plan_left(["bio"])
    settled(qapp, window)
    assert {item["id"] for item in session.blocks} == before_ids
    assert next(item for item in session.blocks if item["id"] == other["id"]) == before_other


def test_1br_overdue_left_minutes_are_placed_plus_unallocated(qapp, window) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    due = (monday + timedelta(days=FRIDAY)).isoformat() + "T23:59"
    session.add_homework({"id": "essay", "title": "Essay", "due": due, "estimate_min": 120, "revision": 0})
    session.save()
    settled(qapp, window)
    block = next(item for item in session.blocks if item.get("assignment_id") == "essay")
    block["duration_min"] = 60
    session._touch()
    assert session.hand_move(block["id"], -1, WEDNESDAY, 15 * 60, 15 * 60 + block["duration_min"])
    session.save()
    settled(qapp, window)
    saturday = datetime.fromisoformat(session.week_start) + timedelta(days=SATURDAY, hours=10)
    session.now_ms = lambda: int(saturday.timestamp() * 1000)
    session.week_changed.emit()
    settled(qapp, window)
    item = next(row for row in session.unfinished() if row["id"] == "essay")
    assert (item["left_over_state"], item["remaining_min"]) == ("overdue", 120)
    assert session.homework_time_needed() == []


def test_1br_plan_overdue_moves_a_future_session(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "16:00"}]})
    settled(qapp, window)
    put_block(session, session_id, SATURDAY, 14 * 60, 15 * 60)
    session.add_block({"id": "class", "title": "Class", "kind": "locked", "days": [SATURDAY],
                       "start": "10:00", "duration_min": 60})
    session.save()
    settled(qapp, window)
    session.plan_left(["bio"])
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    assert (bio["days"], bio["start"]) == ([SATURDAY], "11:00")
    assert session.message == "Placed 1 homework block."
    assert "prefer_earliest" not in bio


def test_1br_overdue_plan_survives_the_next_edit(qapp, window) -> None:
    session_id = overdue_this_week(qapp, window)
    session = window.session
    session.save_preferences({"work_windows": [{"days": [SATURDAY], "start": "10:00", "end": "14:00"}]})
    settled(qapp, window)
    session.add_block({"id": "class", "title": "Class", "kind": "locked", "days": [SATURDAY],
                       "start": "10:00", "duration_min": 60})
    session.save()
    settled(qapp, window)
    session.plan_left(["bio"])
    settled(qapp, window)
    session.add_block({"id": "lunch", "title": "Lunch", "kind": "locked", "days": [SATURDAY],
                       "start": "13:00", "duration_min": 30})
    session.save()
    settled(qapp, window)
    bio = next(item for item in session.blocks if item["id"] == session_id)
    assert (bio["days"], bio["start"]) == ([SATURDAY], "11:00")


def test_1br_failed_overdue_request_does_not_leave_a_new_block(qapp, window, monkeypatch) -> None:
    overdue_this_week(qapp, window)
    session = window.session
    before = [item.copy() for item in session.blocks]
    request = session.client.request

    def fail_plan(method, path, payload, ok, err):
        if path == "/api/solve":
            err(ApiError(503, "The planner is unavailable."))
        else:
            request(method, path, payload, ok, err)

    monkeypatch.setattr(session.client, "request", fail_plan)
    session.plan_left(["bio"])
    settled(qapp, window)
    assert session.blocks == before
    assert session.message == "The planner is unavailable."
