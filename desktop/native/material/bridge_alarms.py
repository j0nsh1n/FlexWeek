"""Alarms in Material: the add and edit sheet's draft, the list rows Settings shows, and the screen an
alarm rings on. The rules are the Widgets Alerts card's: at most 20 alarms, at least one day, a Spotify
link that the engine accepts, a blank name is "Alarm"."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import Property, QObject, Signal, Slot

from desktop.native.spotify import open_in_app

_Done = Callable[[bool], None] | None

MAX_ALARMS = int(flexweek_engine.VIEW_ALARM_MAX)
NO_DAY = str(flexweek_engine.VIEW_ALARM_NO_DAY)
BAD_LINK = str(flexweek_engine.VIEW_ALARM_BAD_LINK)
FULL = str(flexweek_engine.VIEW_ALARM_FULL)
NOT_SAVED = str(flexweek_engine.VIEW_ALARM_NOT_SAVED)
ALARM_SOUNDS = tuple(json.loads(flexweek_engine.VIEW_ALARM_SOUNDS_JSON))
HOURS = tuple(json.loads(flexweek_engine.VIEW_ALARM_HOURS_JSON))
# The same hours for a student on a 12-hour clock: the value stays 0 to 23, the label says AM or PM.
HOURS_12 = tuple(json.loads(flexweek_engine.VIEW_ALARM_HOURS_12_JSON))
MINUTES = tuple(json.loads(flexweek_engine.VIEW_ALARM_MINUTES_JSON))


def alarm_rows(alarms: list[dict]) -> list[dict]:
    """What the list in Alerts shows for each alarm: the name and sound, then when it rings."""
    return json.loads(flexweek_engine.views_alarm_rows(json.dumps(alarms)))


def ring_form(alarm: dict, url: str = "") -> dict[str, Any]:
    """What the alarm-ringing screen and fallback dialog show for a ringing alarm."""
    return json.loads(flexweek_engine.views_ring_form(json.dumps(alarm), url))


class AlarmDraft:
    """One alarm being added or edited. Nothing is stored until `candidate` is saved."""

    def __init__(self, alarm: dict | None, default_sound: str, clock_24h: bool = False) -> None:
        self._core = flexweek_engine.AlarmDraftCore(
            json.dumps(alarm), default_sound, str(uuid4()), clock_24h
        )

    @property
    def existing(self) -> bool:
        return bool(self._core.existing)

    @property
    def clock_24h(self) -> bool:
        return bool(self._core.clock_24h)

    @property
    def id(self) -> str:
        return str(self._core.id)

    @property
    def name(self) -> str:
        return str(self._core.name)

    @property
    def hour(self) -> int:
        return int(self._core.hour)

    @property
    def minute(self) -> int:
        return int(self._core.minute)

    @property
    def days(self) -> list[int]:
        return list(self._core.days)

    @property
    def enabled(self) -> bool:
        return bool(self._core.enabled)

    @property
    def sound(self) -> str:
        return str(self._core.sound)

    @property
    def link(self) -> str:
        return str(self._core.link)

    @property
    def days_problem(self) -> str:
        return str(self._core.days_problem)

    @property
    def link_problem(self) -> str:
        return str(self._core.link_problem)

    @property
    def error(self) -> str:
        return str(self._core.error)

    @error.setter
    def error(self, value: str) -> None:
        self._core.error = value

    def dirty(self) -> bool:
        return bool(self._core.dirty())

    def set_text(self, name: str, value: str) -> None:
        self._core.set_text(name, value)

    def set_number(self, name: str, value: int) -> None:
        self._core.set_number(name, value)

    def set_enabled(self, on: bool) -> None:
        self._core.set_enabled(bool(on))

    def toggle_day(self, day: int) -> None:
        self._core.toggle_day(day)

    def candidate(self) -> dict | None:
        """The alarm as typed, or None with the reason on the field it belongs to."""
        raw = self._core.candidate_json()
        if raw is None:
            return None
        return json.loads(raw)

    def form(self) -> dict[str, Any]:
        return json.loads(self._core.form_json())


class RingBridge(QObject):
    """The screen an alarm rings on. The window plays the sound; this holds what is shown and says what
    the student chose through `done(snoozed)`."""

    changed = Signal()

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("ringBridge")
        self._view = flexweek_engine.RingView()
        self._form: dict[str, Any] = {}
        self._done: _Done = None

    @Property(bool, notify=changed)
    def open(self) -> bool:
        return bool(self._view.open)

    @Property("QVariantMap", notify=changed)  # type: ignore[arg-type]
    def form(self) -> dict[str, Any]:
        return self._form

    def show_alarm(self, alarm: dict, url: str, done: Callable[[bool], None]) -> None:
        self._done = done
        self._form = json.loads(self._view.show_alarm(json.dumps(alarm), url))
        self.changed.emit()

    def show_playing(self, words: str) -> None:
        """What Spotify is playing for this alarm, once it is heard."""
        updated = self._view.show_playing(words)
        if updated is not None:
            self._form = json.loads(updated)
            self.changed.emit()

    def _finish(self, snoozed: bool) -> None:
        if self._view.finish() is None:
            return
        done, self._done = self._done, None
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
        url = self._view.spotify_url()
        if url is not None:
            open_in_app(url)


def with_alarm(alarms: list[dict], made: dict) -> list[dict]:
    """The list with `made` in place of the alarm of its id, or added at the end."""
    return json.loads(flexweek_engine.views_with_alarm(json.dumps(alarms), json.dumps(made)))
