"""Alerts that stay put until the student deals with them (no widget: Material draws the strip)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


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
        self._notices: list[dict] = []
        self._text = ""

    def add(self, notices: list[dict]) -> None:
        self._notices.extend(notices)
        self._render()

    def clear(self) -> None:
        self._notices.clear()
        self._render()

    def pending(self) -> int:
        return len(self._notices)

    def text(self) -> str:
        return self._text

    def drop(self) -> None:
        """One at a time, so a second alert that arrived while the first sat there is still seen."""
        if self._notices:
            self._notices.pop(0)
        self._render()
        if not self._notices:
            self.handled.emit()

    def _render(self) -> None:
        if not self._notices:
            self._text = ""
            self.changed.emit()
            return
        notice = self._notices[0]
        body = notice.get("body") or ""
        more = f"  (+{len(self._notices) - 1} more)" if len(self._notices) > 1 else ""
        self._text = f"{notice.get('title') or 'FlexWeek'}{' — ' + body if body else ''}{more}"
        self.changed.emit()
