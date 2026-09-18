"""Reminder lead windows and alarm snooze. Expected values match app.js."""

from __future__ import annotations

from datetime import datetime

from desktop.native.remind import (
    ALARM_SNOOZE_MS,
    clock_parts,
    due_alarms,
    due_reminders,
    snooze_until,
    start_alert_due,
)


def test_start_alert_due_fires_inside_the_lead_window_only() -> None:
    # 16:00 start, 5 minute lead, 2 minute catch-up window.
    assert start_alert_due(16 * 60, 15 * 60 + 55, 5, 2) is True
    assert start_alert_due(16 * 60, 15 * 60 + 54, 5, 2) is False
    assert start_alert_due(16 * 60, 16 * 60, 5, 2) is False
    assert start_alert_due(16 * 60, 15 * 60 + 57, 5, 2) is True
    assert start_alert_due(16 * 60, 16 * 60, 0, 2) is True
    assert start_alert_due(16 * 60, 15 * 60 + 55, 0, 2) is False


def test_due_reminders_fire_once_per_block_start() -> None:
    blocks = [
        {
            "id": "soccer",
            "title": "Soccer",
            "kind": "locked",
            "start": "16:00",
            "days": [0],
            "completed": False,
            "missed_days": [],
        }
    ]
    fired: set[str] = set()
    first = due_reminders(
        blocks=blocks, trace=None, today_iso="2026-09-14", now_min=15 * 60 + 55, lead_min=5, fired=fired
    )
    assert len(first) == 1
    assert first[0]["title"] == "Soccer starts soon"
    fired.add(first[0]["key"])
    again = due_reminders(
        blocks=blocks, trace=None, today_iso="2026-09-14", now_min=15 * 60 + 56, lead_min=5, fired=fired
    )
    assert again == []
    at_start = due_reminders(
        blocks=blocks, trace=None, today_iso="2026-09-14", now_min=16 * 60, lead_min=0, fired=set()
    )
    assert len(at_start) == 1


def test_completed_and_missed_blocks_do_not_remind() -> None:
    blocks = [
        {
            "id": "done",
            "title": "Done",
            "kind": "locked",
            "start": "16:00",
            "days": [0],
            "completed": True,
            "missed_days": [],
        },
        {
            "id": "missed",
            "title": "Missed",
            "kind": "locked",
            "start": "16:00",
            "days": [0],
            "completed": False,
            "missed_days": [0],
        },
    ]
    assert (
        due_reminders(
            blocks=blocks, trace=None, today_iso="2026-09-14", now_min=15 * 60 + 55, lead_min=5, fired=set()
        )
        == []
    )


def test_alarm_fires_once_then_snoozes_five_minutes() -> None:
    moment = datetime(2026, 9, 14, 7, 0)
    now_ms = int(moment.timestamp() * 1000)
    clock = clock_parts(now_ms)
    alarm = {"id": "wake", "name": "Wake", "time": "07:00", "days": [0], "enabled": True}
    fired: set[str] = set()
    queued, snoozed, last = due_alarms(
        alarms=[alarm],
        today_iso=clock["iso"],
        weekday=clock["day"],
        now_ms=now_ms,
        midnight_ms=clock["midnight_ms"],
        last_check_ms=now_ms - 60_000,
        fired=fired,
        snoozed={},
    )
    assert [item["id"] for item in queued] == ["wake"]
    until = snooze_until(now_ms)
    assert until - now_ms == ALARM_SNOOZE_MS
    later = due_alarms(
        alarms=[alarm],
        today_iso=clock["iso"],
        weekday=clock["day"],
        now_ms=until,
        midnight_ms=clock["midnight_ms"],
        last_check_ms=last,
        fired=fired,
        snoozed={"wake": until},
    )
    assert [item["id"] for item in later[0]] == ["wake"]
    assert later[1] == {}
