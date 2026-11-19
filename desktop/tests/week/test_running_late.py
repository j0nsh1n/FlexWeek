"""Running late: where it starts from, what it names, what the preview says and how Plan treats the
time that has passed."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from backend.tests.fake_clock import CLOCK
from desktop.native.weekmodel import set_clock_24h
from desktop.native.widgets import LateDialog
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.week.support_pastnext import settled_session
from desktop.tests.window_support import qapp, settled  # noqa: F401


def hold_clock(window: NativeWindow, day: int, clock: str) -> None:
    """The one clock at "HH:MM" or "HH:MM:SS" on a day of the open week."""
    hours, minutes, *seconds = (int(part) for part in clock.split(":"))
    CLOCK.set(
        datetime.fromisoformat(window.session.week_start)
        + timedelta(days=day, hours=hours, minutes=minutes, seconds=seconds[0] if seconds else 0)
    )


def running_late_says(
    window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, list[tuple[int, int]]]:
    said: list[str] = []
    asked: list[tuple[int, int]] = []

    def look(dialog: LateDialog) -> int:
        said.extend(label.text() for label in dialog.findChildren(QLabel) if "Starting from" in label.text())
        dialog.preview_requested.emit()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LateDialog, "exec", look)
    monkeypatch.setattr(
        window.session,
        "preview_running_late",
        lambda minutes, now: asked.append((now.hour, now.minute)),
    )
    window._open_late()
    return said[0], asked


# Where it starts ------------------------------------------------------------------------------






def test_running_late_leaves_homework_that_waits_for_a_time_out_of_the_replan(qapp, window) -> None:
    session = window.session
    timed = {
        "id": "essay-1",
        "title": "Essay",
        "kind": "flexible",
        "category": "work",
        "assignment_id": "essay",
        "start": "16:00",
        "duration_min": 60,
        "days": [0],
    }
    waiting = {**timed, "id": "essay-2", "start": None}
    fixed = {
        "id": "gym",
        "title": "Gym",
        "kind": "locked",
        "category": "extra",
        "start": "18:00",
        "duration_min": 60,
        "days": [0],
    }
    session.blocks = [timed, waiting, fixed]
    assert [block["id"] for block in session._late_blocks()] == ["essay-1", "gym"]


# The preview ----------------------------------------------------------------------------------


def _dialog() -> LateDialog:
    set_clock_24h(False)
    dialog = LateDialog(None, "Starting from 5:00 PM today (Monday).")
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                }
            ],
            "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60, "start": "17:15"}],
            "unplaced": [],
        },
        {"late-test": "Late test"},
    )
    return dialog


def _row_labels(dialog: LateDialog) -> list[QLabel]:
    """The row widgets still alive: a cleared row's widget goes at the next event-loop turn."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return dialog.changes.findChildren(QLabel)


def _three_changes() -> dict:
    return {
        "moves": [
            {"block_id": "essay", "from_day": 3, "from_start": "19:00", "to_day": 3, "to_start": "19:30"},
            {"block_id": "poster", "from_day": None, "from_start": None, "to_day": 4, "to_start": "15:30"},
            {"block_id": "sheet", "from_day": None, "from_start": None, "to_day": 4, "to_start": "14:30"},
        ],
        "placed": [
            {"id": "essay", "title": "History essay", "duration_min": 60},
            {"id": "poster", "title": "Science poster", "duration_min": 60},
            {"id": "sheet", "title": "Math worksheet", "duration_min": 60},
        ],
        "unplaced": [],
    }


TITLES = {"essay": "History essay", "poster": "Science poster", "sheet": "Math worksheet"}


def test_running_late_preview_shows_day_and_both_full_ranges(qapp) -> None:
    dialog = _dialog()
    item = dialog.changes.item(0)
    assert item.text() == "Late test: Mon 4:45–5:45 PM → Mon 5:15–6:15 PM"
    assert item.data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Late test, moves from Monday 4:45 to 5:45 PM to Monday 5:15 to 6:15 PM"
    )
    assert dialog.summary.text() == "1 task moves"
    dialog.show_trace({"moves": [], "placed": [], "unplaced": [{"id": "lost", "title": "Lost"}]}, {})
    assert dialog.summary.text() == "Nothing needs to move."
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_names_and_bolds_a_changed_day(qapp) -> None:
    dialog = _dialog()
    trace = {
        "moves": [
            {
                "block_id": "late-test",
                "from_day": 0,
                "from_start": "16:45",
                "to_day": 1,
                "to_start": "17:15",
            }
        ],
        "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60, "start": "17:15"}],
        "unplaced": [],
    }
    dialog.show_trace(trace, {"late-test": "Late test"})
    item = dialog.changes.item(0)
    assert "Tue" in item.text()
    assert "<b>Tue</b>" in dialog.changes.itemWidget(item).text()
    assert "different day" in item.data(Qt.ItemDataRole.AccessibleTextRole)
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_uses_singular_plural_and_omits_zero_counts(qapp) -> None:
    dialog = _dialog()
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                },
                {
                    "block_id": "other",
                    "from_day": 0,
                    "from_start": "18:00",
                    "to_day": 0,
                    "to_start": "18:15",
                },
            ],
            "placed": [
                {"id": "late-test", "title": "Late test", "duration_min": 60},
                {"id": "other", "title": "Other", "duration_min": 60},
            ],
            "unplaced": [{"id": "lost", "title": "Lost"}],
        },
        {"late-test": "Late test", "other": "Other"},
    )
    assert dialog.summary.text() == "2 tasks move"
    dialog.show_trace(
        {
            "moves": [
                {
                    "block_id": "late-test",
                    "from_day": 0,
                    "from_start": "16:45",
                    "to_day": 0,
                    "to_start": "17:15",
                }
            ],
            "placed": [{"id": "late-test", "title": "Late test", "duration_min": 60}],
            "unplaced": [],
        },
        {"late-test": "Late test"},
    )
    assert dialog.summary.text() == "1 task moves"
    set_clock_24h(True)
    dialog.close()


def test_running_late_preview_draws_each_change_once_with_its_title(qapp) -> None:
    set_clock_24h(False)
    dialog = LateDialog(None, "History essay, 7:00 PM, moves 30 min later")
    dialog.show()
    dialog.show_trace(_three_changes(), TITLES)
    assert dialog.changes.count() == 3
    rows = [dialog.changes.item(index) for index in range(3)]
    labels = [dialog.changes.itemWidget(row) for row in rows]
    assert all(isinstance(label, QLabel) for label in labels)
    assert len(_row_labels(dialog)) == 3
    for row, label, title in zip(rows, labels, TITLES.values(), strict=True):
        assert row.text().startswith(title)
        assert title in label.text()
        assert title in row.data(Qt.ItemDataRole.AccessibleTextRole)
    assert rows[1].text() == "Science poster, placed Fri 3:30 PM"
    assert rows[1].data(Qt.ItemDataRole.AccessibleTextRole) == "Science poster, placed Friday 3:30 PM"
    assert rows[0].text() == "History essay: Thu 7–8 PM → Thu 7:30–8:30 PM"
    set_clock_24h(True)
    dialog.close()


def test_running_late_second_preview_replaces_the_rows(qapp) -> None:
    dialog = LateDialog(None, "")
    dialog.show()
    dialog.show_trace(_three_changes(), TITLES)
    dialog.show_trace(_three_changes(), TITLES)
    assert dialog.changes.count() == 3
    assert len(_row_labels(dialog)) == 3
    one = _three_changes()
    one["moves"] = one["moves"][:1]
    dialog.show_trace(one, TITLES)
    assert dialog.changes.count() == 1
    assert dialog.summary.text() == "1 task moves"
    dialog.close()




# Plan and Replan from the time that has passed --------------------------------------------------


def _plan_at_monday_five(qapp: QApplication, window: NativeWindow, *, everything: bool) -> list[dict]:
    session = window.session
    wait_until(qapp, lambda: session.preferences is not None)
    monday = datetime.fromisoformat(session.week_start)
    CLOCK.set(monday + timedelta(hours=17))
    session.add_homework(
        {
            "id": "floor-homework",
            "title": "Floor homework",
            "estimate_min": 60,
            "revision": 0,
            "due": (monday.date() + timedelta(days=3)).isoformat() + "T23:59",
        }
    )
    session.save()
    wait_until(qapp, lambda: not session.busy and not session.dirty)
    settled_session(qapp, session)
    session.solve(everything=everything)
    wait_until(qapp, lambda: not session.planning and not session.busy and not session.dirty, timeout=20)
    settled_session(qapp, session)
    return [block for block in session.blocks if block.get("assignment_id") == "floor-homework"]


def _assert_not_before_monday_five(blocks: list[dict]) -> None:
    for block in blocks:
        if not block.get("start"):
            continue
        day = min(block.get("days") or [0])
        hour, minute = map(int, block["start"].split(":"))
        assert (day, hour * 60 + minute) >= (0, 17 * 60), block


def test_plan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, window) -> None:
    blocks = _plan_at_monday_five(qapp, window, everything=False)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_replan_keeps_everything_at_or_after_now_on_an_empty_monday(qapp, window) -> None:
    blocks = _plan_at_monday_five(qapp, window, everything=True)
    assert any(block.get("start") for block in blocks)
    _assert_not_before_monday_five(blocks)


def test_only_a_times_own_am_pm_is_kept_with_it() -> None:
    from desktop.native.widgets import _unbroken_time

    assert _unbroken_time("PM club AMERICAN: Mon 4:45–5:45 PM → Tue 7 AM") == (
        "PM club AMERICAN: Mon 4:45–5:45 PM → Tue 7 AM"
    )
