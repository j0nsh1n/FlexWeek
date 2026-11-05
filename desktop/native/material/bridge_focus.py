"""The Material Focus screen's bridge: the session's one focus timer, drawn full window.

Nothing is kept here that the session does not hold. The timer, its phase and the presets are
NativeSession's, so the Widgets focus strip and this screen are two views of the same session. The
bridge adds only whether the screen is open, and the words and buttons the screen needs.
"""

from __future__ import annotations

from typing import Any, Protocol

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from shiboken6 import isValid

from desktop.native.focus import format_countdown, phase_duration_ms, remaining_ms

PHASE_WORDS = {"work": "Focus", "break": "Break", "long_break": "Long break", "ended": "Session finished"}
READY_WORDS = "Ready when you are"
QUICK_TITLE = "Quick focus"
SKIP_HINTS = {"work": "Skip to the break", "break": "Skip the break", "long_break": "Skip the break"}
AUDIO_WORDS = {"rain": "Rain", "lo-fi": "Lo-Fi", "white-noise": "White noise", "spotify": "Spotify"}


class _Session(Protocol):
    focus: dict | None
    preferences: dict | None
    assignments: dict

    def now_ms(self) -> int: ...


class FocusBridge(QObject):
    changed = Signal()
    # The screen asks for a yes before it ends a session that has begun.
    endRequested = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("focusBridge")
        self._window = window
        self._open = False
        self._origin_item: QObject | None = None
        self._session().focus_changed.connect(self.refresh)

    def _session(self) -> Any:
        return self._window.session  # type: ignore[attr-defined]

    def refresh(self) -> None:
        """The session's timer moved. A session that is gone has nothing left to show."""
        if self._open and self._session().account is None:
            self._open = False
        self.changed.emit()

    def _state(self) -> dict | None:
        return self._session().focus

    def _phase(self) -> str:
        state = self._state()
        return "ready" if state is None else str(state.get("phase") or "work")

    @Property(bool, notify=changed)
    def open(self) -> bool:
        return self._open

    @Property(str, notify=changed)
    def phase(self) -> str:
        return self._phase()

    @Property(bool, notify=changed)
    def ready(self) -> bool:
        return self._state() is None

    @Property(bool, notify=changed)
    def ended(self) -> bool:
        return self._phase() == "ended"

    @Property(bool, notify=changed)
    def active(self) -> bool:
        """A timer exists and its session has not ended: Skip, Pause and Finish apply."""
        return self._state() is not None and self._phase() != "ended"

    @Property(bool, notify=changed)
    def running(self) -> bool:
        state = self._state()
        return bool(state and state.get("running") and self._phase() != "ended")

    @Property(bool, notify=changed)
    def paused(self) -> bool:
        return self.active and not self.running

    @Property(str, notify=changed)
    def phaseText(self) -> str:
        if self._state() is None:
            return READY_WORDS
        words = PHASE_WORDS.get(self._phase(), "")
        return words + (" · Paused" if self.paused else "")

    @Property(str, notify=changed)
    def title(self) -> str:
        state = self._state()
        return QUICK_TITLE if state is None else str(state.get("title") or QUICK_TITLE)

    @Property(str, notify=changed)
    def timeText(self) -> str:
        session = self._session()
        state = self._state()
        if state is None:
            return format_countdown(phase_duration_ms("work", session.preferences))
        if self._phase() == "ended":
            return format_countdown(0)
        return format_countdown(remaining_ms(state, session.now_ms()))

    @Property(str, notify=changed)
    def pauseText(self) -> str:
        return "Pause" if self.running else "Resume"

    @Property(str, notify=changed)
    def skipHint(self) -> str:
        return SKIP_HINTS.get(self._phase(), "Skip")

    @Property(str, notify=changed)
    def note(self) -> str:
        """What is on for this session, as the mockup says it: "Alerts muted · Rain"."""
        session = self._session()
        words = []
        if session.focus_mutes_alerts():
            words.append("Alerts muted")
        sound = AUDIO_WORDS.get((session.preferences or {}).get("focus_audio") or "")
        if sound and self._state() is not None:
            words.append(sound)
        return " · ".join(words)

    @Property(bool, notify=changed)
    def canFinishHomework(self) -> bool:
        """Time is up on homework that is still open: Finished marks it done."""
        session = self._session()
        state = self._state()
        if state is None or self._phase() != "ended":
            return False
        homework = (session.assignments or {}).get(state.get("assignmentId"))
        return homework is not None and not homework.get("completed")

    @Property(str, notify=changed)
    def endQuestion(self) -> str:
        session = self._session()
        return f"You have done {session.focus_elapsed_min()} min of {self.title}."

    @Slot()
    def show(self) -> None:
        """Open the screen on whatever the timer is doing, ready or running."""
        if self._session().account is None:
            return
        page = getattr(self._window, "_material_page", None)
        quick = getattr(page, "_quick", None) if page is not None else None
        scene = quick.quickWindow() if quick is not None else None
        if scene is not None:
            active = scene.activeFocusItem()
            if active is not None and getattr(active, "objectName", lambda: "")() != "materialFocus":
                self._origin_item = active
        self._open = True
        self.changed.emit()

    @Slot()
    def hide(self) -> None:
        """Leave the screen. The timer keeps going."""
        if self._open:
            self._open = False
            self.changed.emit()
            if self._origin_item is not None:
                item = self._origin_item
                self._origin_item = None

                def _restore() -> None:
                    if not isValid(item):
                        return
                    has_vis = (
                        item.isVisible() if hasattr(item, "isVisible") else bool(item.property("visible"))
                    )
                    has_en = (
                        item.isEnabled() if hasattr(item, "isEnabled") else bool(item.property("enabled"))
                    )
                    if has_vis and has_en and hasattr(item, "forceActiveFocus"):
                        item.forceActiveFocus()

                # Owned by this bridge: a bridge dropped before the turn ends takes the timer with it.
                QTimer.singleShot(0, self, _restore)

    @Slot()
    def begin(self) -> None:
        """Start from Ready: a quick focus that is not tied to any homework."""
        self._session().start_quick_focus()

    @Slot(str, "QVariant", result=bool)
    def startFocus(self, block_id: str, day: object = None) -> bool:
        """Start focus on a block, as the Widgets Start focus does, and open the screen on it."""
        if self._session().start_focus(block_id or None, day if isinstance(day, int) else None):
            self.show()
            return True
        return False

    @Slot()
    def startQuick(self) -> None:
        if self._session().start_quick_focus():
            self.show()

    @Slot()
    def togglePause(self) -> None:
        self._session().toggle_focus_pause()

    @Slot()
    def skip(self) -> None:
        self._session().advance_focus(False)

    @Slot()
    def takeBreak(self) -> None:
        self._session().take_focus_break()

    @Slot()
    def markFinished(self) -> None:
        if self._session().finish_focused_homework():
            self.hide()

    @Slot()
    def finish(self) -> None:
        """Finish and Back both end the session. One that has begun asks first."""
        self._leave()

    @Slot()
    def back(self) -> None:
        self._leave()

    def _leave(self) -> None:
        if self.active:
            self.endRequested.emit()
        elif self._state() is None:
            self.hide()
        else:
            self.confirmEnd()

    @Slot()
    def confirmEnd(self) -> None:
        self._session().reset_focus()
        self.hide()
