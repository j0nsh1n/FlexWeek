"""Alarms in Material: the add and edit sheet's draft, the list rows Settings shows, and the screen an
alarm rings on. The rules are the Widgets Alerts card's: at most 20 alarms, at least one day, a Spotify
link that the engine accepts, a blank name is "Alarm"."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any
from uuid import uuid4

from flexweek_engine import valid_spotify_url  # type: ignore[import-untyped]
from PySide6.QtCore import Property, QObject, Signal, Slot

from desktop.native.calendar import DAY_FULL, DAYS
from desktop.native.remind import ALARM_SNOOZE_MIN
from desktop.native.settings_copy import ring_days
from desktop.native.spotify import open_in_app
from desktop.native.tones import FALLBACK, SOUNDS
from desktop.native.weekmodel import hhmm_text

MAX_ALARMS = 20
NO_DAY = "Pick at least one day."
BAD_LINK = "Use an https://open.spotify.com share link."
FULL = f"You can have up to {MAX_ALARMS} alarms."
NOT_SAVED = "Couldn't save the alarm. Try again."
ALARM_SOUNDS = tuple(
    {"label": "Spotify link" if name == "spotify" else name.title(), "value": name} for name in SOUNDS
)
HOURS = tuple({"label": f"{hour:02d}", "value": hour} for hour in range(24))
# The same hours for a student on a 12-hour clock: the value stays 0 to 23, the label says AM or PM.
HOURS_12 = tuple(
    {"label": f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}", "value": hour} for hour in range(24)
)
MINUTES = tuple({"label": f"{minute:02d}", "value": minute} for minute in range(60))


def alarm_rows(alarms: list[dict]) -> list[dict]:
    """What the list in Alerts shows for each alarm: the name and sound, then when it rings."""
    rows = []
    for alarm in alarms:
        sound = str(alarm.get("sound") or FALLBACK)
        label = "Spotify" if sound == "spotify" else sound.title()
        off = "" if alarm.get("enabled", True) else " · off"
        when = f"Rings at {hhmm_text(str(alarm.get('time')))}, {ring_days(alarm.get('days') or [])}"
        rows.append(
            {
                "id": str(alarm.get("id")),
                "title": f"{alarm.get('name')} · {label}{off}",
                "subtitle": when,
            }
        )
    return rows


class AlarmDraft:
    """One alarm being added or edited. Nothing is stored until `candidate` is saved."""

    def __init__(self, alarm: dict | None, default_sound: str, clock_24h: bool = False) -> None:
        self.existing = alarm is not None
        self.clock_24h = clock_24h
        base = alarm or {}
        self.id = str(base.get("id") or uuid4())
        self.name = str(base.get("name") or "")
        # A usual time to wake, not midnight, as in Widgets.
        hour, _sep, minute = str(base.get("time") or "07:00").partition(":")
        self.hour = int(hour)
        self.minute = int(minute)
        self.days = sorted(base.get("days") or range(5))
        self.enabled = bool(base.get("enabled", True))
        sound = str(base.get("sound") or default_sound)
        self.sound = sound if sound in SOUNDS else FALLBACK
        self.link = str(base.get("spotify_url") or "")
        self.days_problem = ""
        self.link_problem = ""
        self.error = ""
        self._opened_as = self._picture()

    def _picture(self) -> tuple:
        return (
            self.name,
            self.hour,
            self.minute,
            tuple(self.days),
            self.enabled,
            self.sound,
            self.link,
        )

    def dirty(self) -> bool:
        return self._picture() != self._opened_as

    def set_text(self, name: str, value: str) -> None:
        self.error = ""
        if name == "name":
            self.name = value
        elif name == "link":
            self.link = value
            self.link_problem = ""
        elif name == "sound" and value in SOUNDS:
            self.sound = value

    def set_number(self, name: str, value: int) -> None:
        self.error = ""
        if name == "hour" and 0 <= value <= 23:
            self.hour = value
        elif name == "minute" and 0 <= value <= 59:
            self.minute = value

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)

    def toggle_day(self, day: int) -> None:
        if not 0 <= day <= 6:
            return
        self.error = ""
        self.days_problem = ""
        chosen = set(self.days)
        chosen.symmetric_difference_update({day})
        self.days = sorted(chosen)

    def candidate(self) -> dict | None:
        """The alarm as typed, or None with the reason on the field it belongs to."""
        if not self.days:
            # An alarm on no days never rings, so it is refused rather than stored.
            self.days_problem = NO_DAY
            return None
        link = self.link.strip()
        if link:
            try:
                link = valid_spotify_url(link) or ""
            except ValueError:
                self.link_problem = BAD_LINK
                return None
        return {
            "id": self.id,
            "name": self.name.strip() or "Alarm",
            "time": f"{self.hour:02d}:{self.minute:02d}",
            "days": list(self.days),
            "enabled": self.enabled,
            "sound": self.sound,
            "spotify_url": link or None,
        }

    def form(self) -> dict[str, Any]:
        return {
            "kind": "alarm",
            "heading": "Edit alarm" if self.existing else "New alarm",
            "name": self.name,
            "hour": self.hour,
            "minute": self.minute,
            "hours": list(HOURS if self.clock_24h else HOURS_12),
            "minutes": list(MINUTES),
            "days": [{"label": DAYS[day], "full": DAY_FULL[day], "on": day in self.days} for day in range(7)],
            "enabled": self.enabled,
            "sound": self.sound,
            "sounds": list(ALARM_SOUNDS),
            "link": self.link,
            "linkProblem": self.link_problem,
            "daysProblem": self.days_problem,
            "canRemove": self.existing,
            "error": self.error,
        }


class RingBridge(QObject):
    """The screen an alarm rings on. The window plays the sound; this holds what is shown and says what
    the student chose through `done(snoozed)`."""

    changed = Signal()

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("ringBridge")
        self._open = False
        self._form: dict[str, Any] = {}
        self._url = ""
        self._done: Callable[[bool], None] | None = None

    @Property(bool, notify=changed)
    def open(self) -> bool:
        return self._open

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def form(self) -> dict[str, Any]:
        return self._form

    def show_alarm(self, alarm: dict, url: str, done: Callable[[bool], None]) -> None:
        ringing = "Starting now" if alarm.get("block") else "Alarm is ringing"
        when = str(alarm.get("time") or "")
        self._url = url
        self._done = done
        self._form = {
            "title": str(alarm.get("name") or "Alarm"),
            "detail": f"{hhmm_text(when) if when else ''} · {ringing}",
            "spotify": bool(url),
            "playing": "",
            "snoozeLabel": f"Snooze {ALARM_SNOOZE_MIN} minutes",
        }
        self._open = True
        self.changed.emit()

    def show_playing(self, words: str) -> None:
        """What Spotify is playing for this alarm, once it is heard."""
        if self._open:
            self._form = {**self._form, "playing": words}
            self.changed.emit()

    def _finish(self, snoozed: bool) -> None:
        if not self._open:
            return
        done, self._done = self._done, None
        self._open = False
        self._form = {}
        self.changed.emit()
        if done is not None:
            done(snoozed)

    @Slot()
    def dismiss(self) -> None:
        self._finish(False)

    @Slot()
    def snooze(self) -> None:
        self._finish(True)

    @Slot()
    def openSpotify(self) -> None:
        if self._url:
            open_in_app(self._url)


def with_alarm(alarms: list[dict], made: dict) -> list[dict]:
    """The list with `made` in place of the alarm of its id, or added at the end."""
    out = deepcopy(alarms)
    for index, item in enumerate(out):
        if item.get("id") == made["id"]:
            out[index] = made
            return out
    out.append(made)
    return out
