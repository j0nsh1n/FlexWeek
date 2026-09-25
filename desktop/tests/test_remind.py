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


def test_start_alert_due_from_the_lead_to_the_start() -> None:
    # 16:00 start, 5 minute lead: due from 15:55 through the 16:00 minute, never after.
    assert start_alert_due(16 * 60, 15 * 60 + 55, 5) is True
    assert start_alert_due(16 * 60, 15 * 60 + 54, 5) is False
    assert start_alert_due(16 * 60, 15 * 60 + 58, 5) is True
    assert start_alert_due(16 * 60, 16 * 60, 5) is True
    assert start_alert_due(16 * 60, 16 * 60 + 1, 5) is False
    assert start_alert_due(16 * 60, 16 * 60, 0) is True
    assert start_alert_due(16 * 60, 15 * 60 + 55, 0) is False


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


def test_alarm_fires_at_seven_on_a_daylight_saving_day() -> None:
    import os
    import time

    previous = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    try:
        alarm = {"id": "wake", "name": "Wake", "time": "07:00", "days": [6], "enabled": True}

        def queued_at(iso: str) -> list[str]:
            moment = datetime.fromisoformat(iso).replace(hour=7, minute=0)
            now_ms = int(moment.timestamp() * 1000)
            clock = clock_parts(now_ms)
            queued, _, _ = due_alarms(
                alarms=[alarm],
                today_iso=iso,
                weekday=moment.weekday(),
                now_ms=now_ms,
                midnight_ms=clock["midnight_ms"],
                last_check_ms=now_ms - 60_000,
                fired=set(),
                snoozed={},
            )
            return [item["id"] for item in queued]

        assert queued_at("2026-03-08") == ["wake"]
        assert queued_at("2026-11-01") == ["wake"]
        assert queued_at("2026-09-13") == ["wake"]
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


PRACTICE = {
    "id": "practice",
    "title": "Guitar practice",
    "kind": "locked",
    "start": "18:45",
    "days": [3],
    "completed": False,
    "missed_days": [],
}
THURSDAY = "2026-09-17"


def reminded(minutes: range, lead: int, block: dict = PRACTICE) -> list[tuple[int, str]]:
    """Each minute checked in turn, as the poll does, keeping what has fired."""
    fired: set[str] = set()
    seen = []
    for minute in minutes:
        for item in due_reminders(
            blocks=[block], trace=None, today_iso=THURSDAY, now_min=minute, lead_min=lead, fired=fired
        ):
            fired.add(item["key"])
            seen.append((minute, item["title"]))
    return seen


def test_a_block_first_seen_inside_its_lead_reminds_at_the_first_check() -> None:
    # Saved at 18:38 for 18:45 with a 10-minute lead: the lead began at 18:35.
    assert reminded(range(18 * 60 + 38, 19 * 60), lead=10) == [(18 * 60 + 38, "Guitar practice starts soon")]


def test_a_block_first_seen_in_its_start_minute_says_it_starts_now() -> None:
    assert reminded(range(18 * 60 + 45, 19 * 60), lead=10) == [(18 * 60 + 45, "Guitar practice starts now")]


def test_a_block_that_has_started_does_not_remind() -> None:
    assert reminded(range(18 * 60 + 46, 19 * 60), lead=10) == []


def test_a_block_with_a_song_is_announced_by_the_song_at_its_start() -> None:
    from desktop.native.remind import due_songs

    block = {**PRACTICE, "spotify_url": "https://open.spotify.com/track/abc"}
    assert reminded(range(18 * 60 + 45, 19 * 60), lead=0, block=block) == []
    played: set[str] = set()
    songs = []
    for minute in range(18 * 60 + 40, 19 * 60):
        for song in due_songs(blocks=[block], trace=None, today_iso=THURSDAY, now_min=minute, played=played):
            played.add(song["id"])
            songs.append((minute, song["name"], song["spotify_url"]))
    assert songs == [(18 * 60 + 45, "Guitar practice", "https://open.spotify.com/track/abc")]
    start = 18 * 60 + 45
    assert due_songs(blocks=[PRACTICE], trace=None, today_iso=THURSDAY, now_min=start, played=set()) == []
