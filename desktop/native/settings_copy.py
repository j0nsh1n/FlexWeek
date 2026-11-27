"""Choices and wording that Settings and the account setup both show."""

from __future__ import annotations

import json
from datetime import datetime

import flexweek_engine  # type: ignore[import-untyped]

SPORT_FALLBACK = flexweek_engine.VIEW_SPORT_FALLBACK
ALARM_TONE_LABELS = flexweek_engine.VIEW_ALARM_TONE_LABELS
ALARM_NOTE = flexweek_engine.VIEW_ALARM_NOTE
DRAG_STEP_QUESTION = flexweek_engine.VIEW_DRAG_STEP_QUESTION
DRAG_STEP_CHOICES = flexweek_engine.VIEW_DRAG_STEP_CHOICES
PLANNING_STYLES = flexweek_engine.VIEW_PLANNING_STYLES
SPOTIFY_LINK_HINT = flexweek_engine.VIEW_SPOTIFY_LINK_HINT
SPOTIFY_TONE_REST = flexweek_engine.VIEW_SPOTIFY_TONE_REST
SPOTIFY_TONE_NOTE = flexweek_engine.VIEW_SPOTIFY_TONE_NOTE
STUDY_HOURS_LINE = flexweek_engine.VIEW_STUDY_HOURS_LINE
SCHOOL_HOURS_NOTE = flexweek_engine.VIEW_SCHOOL_HOURS_NOTE
NO_SCHOOL_DAYS = flexweek_engine.VIEW_NO_SCHOOL_DAYS
NO_STUDY_HOURS = flexweek_engine.VIEW_NO_STUDY_HOURS
NO_PROTECTED = flexweek_engine.VIEW_NO_PROTECTED
PROTECTED_WORDS = flexweek_engine.VIEW_PROTECTED_WORDS
DND_NOTE = flexweek_engine.VIEW_DND_NOTE
TRAY_NOTE = flexweek_engine.VIEW_TRAY_NOTE
BLOCK_SONG_NOTE = flexweek_engine.VIEW_BLOCK_SONG_NOTE
FOCUS_AUDIO_NOTE = flexweek_engine.VIEW_FOCUS_AUDIO_NOTE
NO_SOUND = flexweek_engine.VIEW_NO_SOUND
SPLIT_ROUNDED = flexweek_engine.VIEW_SPLIT_ROUNDED
ABOUT_LINE = flexweek_engine.VIEW_ABOUT_LINE
ABOUT_HERE = flexweek_engine.VIEW_ABOUT_HERE
HELP_SCREENS = flexweek_engine.VIEW_HELP_SCREENS
HELP_PLANNING = flexweek_engine.VIEW_HELP_PLANNING
HELP_PLANNING_MATERIAL = flexweek_engine.VIEW_HELP_PLANNING_MATERIAL
HELP_NUMBER_KEYS = flexweek_engine.VIEW_HELP_NUMBER_KEYS
HELP_LETTER_KEYS = flexweek_engine.VIEW_HELP_LETTER_KEYS
HELP_OTHER_KEYS = flexweek_engine.VIEW_HELP_OTHER_KEYS
HELP_KEYS = flexweek_engine.VIEW_HELP_KEYS
ACCOUNT_PASSWORD_NOTE = flexweek_engine.VIEW_ACCOUNT_PASSWORD_NOTE
ACCOUNT_CODES_NOTE = flexweek_engine.VIEW_ACCOUNT_CODES_NOTE
ACCOUNT_DATA_NOTE = flexweek_engine.VIEW_ACCOUNT_DATA_NOTE
RESTORE_FIRST = flexweek_engine.VIEW_RESTORE_FIRST
RELAY_SENTENCE = flexweek_engine.VIEW_RELAY_SENTENCE
UNREACHABLE_WORDS = flexweek_engine.VIEW_UNREACHABLE_WORDS
DOT_WORDS = flexweek_engine.VIEW_DOT_WORDS
PAIR_ONCE = flexweek_engine.VIEW_PAIR_ONCE
PAIR_CLOSED = flexweek_engine.VIEW_PAIR_CLOSED


def ring_days(days: list[int]) -> str:
    """The days an alarm rings, as a student would say them."""
    return flexweek_engine.view_ring_days(json.dumps(days))


def help_keys(numbers: bool, letters: bool, *, material: bool = False) -> tuple[tuple[str, str], ...]:
    """Help's keys as the look answers to them."""
    return tuple(flexweek_engine.view_help_keys(numbers, letters, material=material))


def keys_words(marked: str) -> str:
    """A shortcut as it is said: its keys without their brackets."""
    return flexweek_engine.view_keys_words(marked)


def first_lines(notes: str, limit: int = 6) -> str:
    """The top of the release notes, with the markers these notes use turned into plain lines."""
    return flexweek_engine.view_first_lines(notes, limit)


def key_parts(marked: str) -> list[tuple[str, bool]]:
    """A shortcut as (text, is_key) pieces: each key in brackets, then the plain words between them."""
    return flexweek_engine.view_key_parts(marked)


def recovery_status(remaining: int | None) -> str:
    """How many recovery codes are left, in the words the account dialog uses."""
    return flexweek_engine.view_recovery_status(json.dumps(remaining))


def restore_parts(point: dict) -> tuple[str, str]:
    """A restore point as its name and, apart, when it was made and how many weeks it holds."""
    return flexweek_engine.view_restore_parts(json.dumps(point))


def restore_row(point: dict) -> str:
    """One restore point in the list: its name, when it was made and how many weeks it holds."""
    return flexweek_engine.view_restore_row(json.dumps(point))


def restore_summary(preview: dict | None) -> str:
    """What going back to the previewed restore point would change."""
    return flexweek_engine.view_restore_summary(json.dumps(preview))


def transfer_summary(preview: dict) -> str:
    """What importing a backup file will do, in sentences."""
    return flexweek_engine.view_transfer_summary(json.dumps(preview))


def seen_words(last_seen_ms: str | None, now_ms: int) -> str:
    """When a phone was last seen, in the card's words. last_seen is Unix milliseconds as text."""
    return flexweek_engine.view_seen_words(last_seen_ms, now_ms, _seen_weekday(last_seen_ms))


def _seen_weekday(last_seen_ms: str | None) -> str:
    """The computer's own weekday name for a phone's last-seen instant. Rust takes no clock or zone."""
    if not last_seen_ms:
        return ""
    return datetime.fromtimestamp(int(last_seen_ms) / 1000).strftime("%A")


def clock_warning_words(count: int) -> str:
    return flexweek_engine.view_clock_warning_words(count)


def sync_state(status: dict, linked: bool) -> str:
    """Which picture the status dot shows. A failed call stays a problem until one call works."""
    return flexweek_engine.view_sync_state(json.dumps(status), linked)


def countdown_words(seconds: int) -> str:
    return flexweek_engine.view_countdown_words(seconds)


def tries_words(tries: int) -> str:
    return flexweek_engine.view_tries_words(tries)


def pair_problem(state: str) -> str:
    return flexweek_engine.view_pair_problem(state)
