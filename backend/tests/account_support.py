"""What the account and storage tests share: the headers a browser sends, one sample password, and the
sample bodies they save. Test files import from here; nothing in it asserts."""

from __future__ import annotations

import hashlib
from datetime import timedelta

from backend.tests.fake_clock import START

WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
HOSTED_WRITE = {"X-FlexWeek-Request": "1", "Origin": "https://flexweek.example"}
PASSWORD = "a-long-test-password"
REPLACEMENT = "replacement-pw-1"
# A Monday in September 2026, far from the fake clock's week, so a test that names a week asks for it.
WEEK = "2026-09-14"
# The week a parameterless /api/week answers with, worked out from the fake clock rather than from the
# code under test.
THIS_WEEK = (START.date() - timedelta(days=START.date().weekday())).isoformat()


def preferences(theme: str = "system") -> dict:
    """The preferences body of a new account, with the theme a test wants."""
    return {
        "theme": theme,
        "reminders_enabled": True,
        "reminder_lead_min": 5,
        "reminder_sound": True,
        "reminder_dnd_override": False,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
        "auto_split_pomodoro": False,
        "default_spotify_url": None,
        "alarms": [],
    }


def school() -> dict:
    """A locked school block, Monday to Friday."""
    return {
        "id": "school",
        "title": "School",
        "kind": "locked",
        "duration_min": 390,
        "days": [0, 1, 2, 3, 4],
        "priority": 1,
        "energy": "medium",
        "start": "08:00",
        "category": "School",
    }


def assignment(**overrides) -> dict:
    """A homework item body as the app saves it; `overrides` replace single fields."""
    body = {
        "id": "hw-essay",
        "title": "Essay",
        "course": None,
        "category": "Homework",
        "priority": 3,
        "energy": "medium",
        "spotify_url": None,
        "due": "2026-09-16T23:59",
        "estimate_min": 120,
        "focus_minutes": 0,
        "focus_sessions": 0,
        "completed": False,
        "completed_at": None,
        "revision": 0,
    }
    body.update(overrides)
    return body


def flex(block_id: str, **overrides) -> dict:
    """A flexible homework block of an hour on Monday."""
    block = {
        "id": block_id,
        "title": "Homework",
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "earliest": None,
        "latest": None,
        "start": None,
        "course": None,
    }
    block.update(overrides)
    return block


def migrated_session(block: dict, week_start: str = THIS_WEEK) -> dict:
    """How a saved flexible block reads back: linked to the homework item the save made for it."""
    body = dict(block)
    body["latest"] = None
    body["assignment_id"] = "a-" + hashlib.sha256(f"{week_start}:{block['id']}".encode()).hexdigest()[:32]
    body.pop("focus_minutes", None)
    body.pop("focus_sessions", None)
    return body
