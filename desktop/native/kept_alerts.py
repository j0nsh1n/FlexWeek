"""Alerts that stay put until the student deals with them (no widget: Material draws them)."""

from __future__ import annotations

import json
from collections.abc import Callable

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, Signal


class KeptReminders(QObject):
    """A reminder kept on screen as a card with Snooze and Close, until its block starts.

    The cards and their timing are the engine's (`flexweek_engine.ReminderCards`); this reads the
    clock and today's blocks, and turns what the engine answers into signals. `rows` is today's blocks
    by reminder key, or None when they are not known (another week is open), and `minute` is the
    minute of the local day. `release` is told which key's card went because its block started, so
    the "starts now" notice can take over.
    """

    # What the cards show changed.
    changed = Signal()
    # A card appeared or came back from Snooze: the words a screen reader says.
    shown = Signal(str)

    def __init__(
        self,
        rows: Callable[[], dict[str, dict] | None],
        minute: Callable[[], int],
        release: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows, self._minute, self._release = rows, minute, release
        self._cards = flexweek_engine.ReminderCards()

    def _titles(self) -> str:
        """Today's blocks as reminder key to title, as JSON text; null when they are not known."""
        rows = self._rows()
        if rows is None:
            return "null"
        return json.dumps({key: block.get("title") for key, block in rows.items()}, default=str)

    def add(self, notice: dict) -> bool:
        """Keep this reminder as a card. False when it cannot stay: no key, or its block has started."""
        answer = json.loads(self._cards.add(json.dumps(notice, default=str), self._titles(), self._minute()))
        if answer["said"] is not None:
            self.shown.emit(answer["said"])
        if answer["changed"]:
            self.changed.emit()
        return answer["kept"]

    def cards(self) -> list[dict]:
        """The cards on screen, newest first; a snoozed one is not among them."""
        return json.loads(self._cards.cards())

    def snooze(self, key: str) -> None:
        if self._cards.snooze(key, self._minute()):
            self.changed.emit()

    def close(self, key: str) -> None:
        if self._cards.close(key):
            self.changed.emit()

    def clear(self) -> None:
        if self._cards.clear():
            self.changed.emit()

    def sync(self) -> None:
        """Follow the clock and the week: a card whose block started, moved or went is dropped, a
        snoozed one that is due comes back, and a renamed block's card shows the new name."""
        if not self._cards.has_cards():
            return
        titles = self._titles()
        if titles == "null":
            return
        answer = json.loads(self._cards.sync(titles, self._minute()))
        for words in answer["said"]:
            self.shown.emit(words)
        for key in answer["released"]:
            self._release(key)
        if answer["changed"]:
            self.changed.emit()


class KeptAlerts(QObject):
    """A tray message is gone in eight seconds, and on a machine that suppresses notifications it is
    never seen at all. "Leave reminders on screen" promises the opposite, so when it is on the alert is
    also kept here, in the window, where nothing outside the app can take it away.
    """

    # The student has dealt with every alert it held.
    handled = Signal()
    # What the strip says changed; Material draws its own strip from the same list.
    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._strip = flexweek_engine.AlertStrip()

    def add(self, notices: list[dict]) -> None:
        self._strip.add(json.dumps(notices, default=str))
        self.changed.emit()

    def clear(self) -> None:
        self._strip.clear()
        self.changed.emit()

    def pending(self) -> int:
        return self._strip.pending()

    def text(self) -> str:
        return self._strip.text()

    def drop(self) -> None:
        """One at a time, so a second alert that arrived while the first sat there is still seen."""
        handled = self._strip.drop()
        self.changed.emit()
        if handled:
            self.handled.emit()
