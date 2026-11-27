"""The Material Focus screen's bridge: the session's one focus timer, drawn full window.

Nothing is kept here that the session does not hold. The timer, its phase and the presets are
NativeSession's, so the Widgets focus strip and this screen are two views of the same session. The
bridge adds only whether the screen is open, and the words and buttons the screen needs.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from shiboken6 import isValid

# The words live in the engine's Focus view-model; these names stay for callers that read them.
_WORDS = json.loads(flexweek_engine.views_focus_words())
PHASE_WORDS = _WORDS["phase_words"]
READY_WORDS = _WORDS["ready_words"]
QUICK_TITLE = _WORDS["quick_title"]
SKIP_HINTS = _WORDS["skip_hints"]
AUDIO_WORDS = _WORDS["audio_words"]


class _Session(Protocol):
    focus: dict | None
    preferences: dict | None
    assignments: dict

    def now_ms(self) -> int: ...

    def quick_focus_offer(self) -> dict | None: ...

    def start_focus_on_offer(self) -> bool: ...

    def start_quick_focus(self) -> bool: ...


class FocusBridge(QObject):
    _origin_item: QObject | None
    changed = Signal()
    # The screen asks for a yes before it ends a session that has begun.
    endRequested = Signal()

    def __init__(self, window: QObject, parent: QObject) -> None:
        super().__init__(parent)
        self.setObjectName("focusBridge")
        self._window = window
        self._open = False
        self._origin_item = None
        self._session().focus_changed.connect(self.refresh)

    def _session(self) -> Any:
        return self._window.session  # type: ignore[attr-defined]

    def refresh(self) -> None:
        """The session's timer moved. A session that is gone has nothing left to show."""
        self._open = flexweek_engine.views_focus_refresh_open(self._open, self._session().account is None)
        self.changed.emit()

    def _state(self) -> dict | None:
        return self._session().focus

    def _state_json(self) -> str:
        return json.dumps(self._state())

    def _do(self, step: str) -> None:
        """Run the step the engine chose. The names are the engine's; each maps to one Qt call."""
        {
            "hide": self.hide,
            "show": self.show,
            "request_end": self.endRequested.emit,
            "confirm_end": self.confirmEnd,
            "stay": self._stay,
        }[step]()

    def _stay(self) -> None:
        """The engine chose to leave things as they are."""

    @Property(bool, notify=changed)
    def open(self) -> bool:
        return self._open

    @Property(str, notify=changed)
    def phase(self) -> str:
        return flexweek_engine.views_focus_phase(self._state_json())

    @Property(bool, notify=changed)
    def ready(self) -> bool:
        return flexweek_engine.views_focus_ready(self._state_json())

    @Property(bool, notify=changed)
    def ended(self) -> bool:
        return flexweek_engine.views_focus_ended(self._state_json())

    @Property(bool, notify=changed)
    def active(self) -> bool:
        """A timer exists and its session has not ended: Skip, Pause and Finish apply."""
        return flexweek_engine.views_focus_active(self._state_json())

    @Property(bool, notify=changed)
    def running(self) -> bool:
        return flexweek_engine.views_focus_running(self._state_json())

    @Property(bool, notify=changed)
    def paused(self) -> bool:
        return flexweek_engine.views_focus_paused(self._state_json())

    @Property(str, notify=changed)
    def phaseText(self) -> str:
        return flexweek_engine.views_focus_phase_text(self._state_json())

    @Property(str, notify=changed)
    def title(self) -> str:
        return flexweek_engine.views_focus_title(self._state_json(), self._offer_json())

    def _offer(self) -> dict | None:
        """The homework on now or next today, while Ready; a running timer has already chosen."""
        if self._state() is None:
            return self._session().quick_focus_offer()
        return None

    def _offer_json(self) -> str:
        return json.dumps(self._offer())

    @Property(bool, notify=changed)
    def offered(self) -> bool:
        """Ready with homework on now or next today: Start counts toward it and Just a timer does not."""
        return flexweek_engine.views_focus_offered(self._state_json(), self._offer_json())

    @Property(str, notify=changed)
    def timeText(self) -> str:
        session = self._session()
        return flexweek_engine.views_focus_time_text(
            self._state_json(), json.dumps(session.preferences), session.now_ms()
        )

    @Property(str, notify=changed)
    def pauseText(self) -> str:
        return flexweek_engine.views_focus_pause_text(self._state_json())

    @Property(str, notify=changed)
    def skipHint(self) -> str:
        return flexweek_engine.views_focus_skip_hint(self._state_json())

    @Property(str, notify=changed)
    def note(self) -> str:
        """What is on for this session, as the mockup says it: "Alerts muted · Rain"."""
        session = self._session()
        return flexweek_engine.views_focus_note(
            self._state_json(), json.dumps(session.preferences), session.focus_mutes_alerts()
        )

    @Property(bool, notify=changed)
    def canFinishHomework(self) -> bool:
        """Time is up on homework that is still open: Finished marks it done."""
        return flexweek_engine.views_focus_can_finish_homework(
            self._state_json(), json.dumps(self._session().assignments)
        )

    @Property(str, notify=changed)
    def endQuestion(self) -> str:
        session = self._session()
        return flexweek_engine.views_focus_end_question(
            self._state_json(), json.dumps(session.assignments), self.title, session.focus_elapsed_min()
        )

    @Slot()
    def show(self) -> None:
        """Open the screen on whatever the timer is doing, ready or running."""
        if self._session().account is None:
            return
        # Material's window is itself the QQuickWindow whose keyboard focus is read.
        scene = getattr(self._window, "_material_page", None)
        if scene is not None:
            active = scene.activeFocusItem()
            if active is not None and flexweek_engine.views_focus_remembers_origin(
                getattr(active, "objectName", lambda: "")()
            ):
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
                    if flexweek_engine.views_focus_restores_origin(
                        has_vis, has_en, hasattr(item, "forceActiveFocus")
                    ):
                        item.forceActiveFocus()

                # Owned by this bridge: a bridge dropped before the turn ends takes the timer with it.
                QTimer.singleShot(0, self, _restore)

    @Slot()
    def begin(self) -> None:
        """Start from Ready: on the homework the screen names, or a plain timer when none is offered."""
        self._session().start_focus_on_offer()

    @Slot()
    def beginTimer(self) -> None:  # noqa: N802 - the name QML calls
        """Just a timer: a quick focus that is not tied to any homework."""
        self._session().start_quick_focus()

    @Slot(str, "QVariant", result=bool)
    def startFocus(self, block_id: str, day: object = None) -> bool:
        """Start focus on a block, as the Widgets Start focus does, and open the screen on it."""
        block, when = flexweek_engine.views_focus_start_args(block_id, day)
        started = bool(self._session().start_focus(block, when))
        self._do(flexweek_engine.views_focus_after_start_step(started))
        return started

    @Slot()
    def startQuick(self) -> None:
        self._do(flexweek_engine.views_focus_after_start_step(bool(self._session().start_quick_focus())))

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
        # Queued still closes the screen: the week is loading behind it, and the homework
        # finishes when that load lands. A failed load leaves the ended timer for the next open.
        outcome = self._session().finish_focused_homework()
        self._do(flexweek_engine.views_focus_finish_step(outcome))

    @Slot()
    def finish(self) -> None:
        """Finish ends the session. One that has begun asks first."""
        self._leave()

    @Slot()
    def back(self) -> None:
        # A running or paused timer keeps going behind the other screens; a finished one has
        # nothing left to keep, so leaving clears it as Finish does.
        self._do(flexweek_engine.views_focus_back_step(self._state_json()))

    def _leave(self) -> None:
        self._do(flexweek_engine.views_focus_leave_step(self._state_json()))

    @Slot()
    def confirmEnd(self) -> None:
        self._session().end_focus_early()
        self.hide()
