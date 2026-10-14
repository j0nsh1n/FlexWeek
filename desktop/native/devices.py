"""Phones linked to this computer: the Devices card in Settings, the pairing sheet, the sync status
dot in the week's status strip, and the start-up of the sync service itself."""

from __future__ import annotations

import socket
import sqlite3
import sys
import threading
import weakref
from collections.abc import Callable
from contextlib import closing, suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from flexweek_engine import SyncError, SyncService  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from shiboken6 import isValid

from desktop.native.feel import current
from desktop.native.widgets import Dialog, sheet_button, sheet_footer

SYNC_SCAN_MS = 1000
# The whole of one "Sync now" call. flexweek-sync's own default is 45 s.
SYNC_DEADLINE_MS = 45_000
PAIR_TICK_MS = 1000
RELAY_SENTENCE = (
    "When your computer isn't on the same Wi-Fi, FlexWeek uses a public relay run by n0. "
    "It sees that two devices are talking, not what they send."
)
UNREACHABLE_WORDS = "Could not reach your phone. Make sure FlexWeek is open on it."
NO_SYNC_WORDS = "Syncing isn't available on this computer right now. Your week is still saved here."
NO_PHONE_WORDS = "No phone is linked yet."
DOT_WORDS = {
    "off": "",
    "idle": "Waiting for a linked phone to sync",
    "syncing": "Syncing with your phone",
    "synced": "Synced with your phone",
    "problem": "Could not reach your phone",
}


def start_service(database: Path) -> SyncService | None:
    """This computer's sync service for its own database, or None when it cannot start. The rest of
    FlexWeek works without it."""
    key = database.parent / "sync" / "device.key"
    try:
        key.parent.mkdir(parents=True, exist_ok=True)
        return SyncService.start(
            str(database), str(key), socket.gethostname() or "This computer", False, None, SYNC_SCAN_MS
        )
    except (OSError, SyncError) as error:
        print(f"FlexWeek sync did not start: {error}", file=sys.stderr)
        return None


def linked_phone_at_launch(database: Path) -> bool:
    """True when the database already holds a phone that was not removed. Read-only, so a database or
    table that does not exist yet counts as no phone and creates nothing."""
    try:
        with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as conn:
            row = conn.execute("SELECT 1 FROM sync_peer WHERE revoked = 0 LIMIT 1").fetchone()
    except sqlite3.Error:
        return False
    return row is not None


class SyncHost(QObject):
    """Holds this computer's sync service. It starts only when a phone is already linked at launch or
    when the student presses Pair a phone, and never on the window's thread. Once started it runs until
    the app quits. With no service, FlexWeek opens no network endpoint."""

    started = Signal(object)

    def __init__(self, database: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self.service: SyncService | None = None
        self._waiting: list[Callable[[SyncService | None], None]] = []

    @property
    def starting(self) -> bool:
        return bool(self._waiting)

    def start_if_paired(self) -> None:
        if linked_phone_at_launch(self.database):
            self.ensure(lambda _service: None)

    def ensure(self, ready: Callable[[SyncService | None], None]) -> None:
        """Calls `ready` with the running service, now if it runs, otherwise once it has started (None
        when it could not start). Only the first call starts it."""
        if self.service is not None:
            ready(self.service)
            return
        self._waiting.append(ready)
        if len(self._waiting) == 1:
            run_off_ui(self, lambda: start_service(self.database), self._started)

    def _started(self, service: SyncService | None, _problem: Exception | None) -> None:
        self.service = service
        waiting, self._waiting = self._waiting, []
        if service is not None:
            self.started.emit(service)
        for ready in waiting:
            ready(service)

    def stop(self) -> None:
        if self.service is not None:
            self.service.stop()


def live_phones(sync: SyncService, user_id: int | None) -> list[dict]:
    if user_id is None:
        return []
    return [row for row in sync.peers(user_id) if not row["revoked"]]


def seen_words(last_seen_ms: str | None, now_ms: int) -> str:
    """When a phone last synced, in the card's words. last_seen is Unix milliseconds as text."""
    if not last_seen_ms:
        return "Not synced yet"
    seen = int(last_seen_ms)
    minutes = max(0, now_ms - seen) // 60_000
    if minutes < 1:
        return "Synced just now"
    if minutes < 60:
        return f"Synced {minutes} min ago"
    if minutes < 24 * 60:
        return f"Synced {minutes // 60} h ago"
    return f"Not seen since {datetime.fromtimestamp(seen / 1000):%A}"


def countdown_words(seconds: int) -> str:
    minutes, rest = divmod(max(0, seconds), 60)
    return f"Code works for {minutes}:{rest:02d}"


def clock_warning_words(count: int) -> str:
    if count <= 0:
        return ""
    noun, verb = ("change", "was") if count == 1 else ("changes", "were")
    return f"Your phone's clock looks wrong. {count} {noun} {verb} held back."


def tries_words(tries: int) -> str:
    return "1 try left" if tries == 1 else f"{tries} tries left"


def sync_state(status: dict, linked: bool) -> str:
    """Which picture the status dot shows. A failed call stays a problem until one call works."""
    if not linked:
        return "off"
    if status["syncing"]:
        return "syncing"
    if status["last_error"]:
        return "problem"
    if status["last_sync_ms"] is None:
        return "idle"
    return "synced"


def pair_problem(state: str) -> str:
    if state == "expired":
        return "That code has expired. Start a new one."
    if state == "too_many_tries":
        return "Too many wrong tries. Start a new code."
    return ""


class _Answer(QObject):
    ready = Signal(object, object)


# Sync calls still running, each with its answer, held on the window's thread (see run_off_ui).
_IN_FLIGHT: set[tuple[_Answer, threading.Thread]] = set()
RELEASE_RETRY_MS = 20


def run_off_ui(
    owner: QObject, work: Callable[[], Any], done: Callable[[Any, Exception | None], None]
) -> None:
    """Runs `work` on a worker thread, then `done(result, problem)` on the window's thread. The sync
    calls block for up to a few seconds, so none of them may run on the window's thread."""
    # No parent: a parent freed while the call ran (Pair a phone closed) deleted the answer with it, under
    # the worker emitting on it, and the app crashed. _IN_FLIGHT keeps it until the worker has ended.
    answer = _Answer()
    owner_ref = weakref.ref(owner)
    if getattr(done, "__self__", None) is not None:
        done_ref = weakref.WeakMethod(done)
    else:
        def done_ref() -> Callable[[Any, Exception | None], None]:
            return done

    def deliver(result: Any, problem: Exception | None) -> None:
        live_owner = owner_ref()
        live_done = done_ref()
        if live_owner is not None and live_done is not None and isValid(live_owner):
            live_done(result, problem)

    def run() -> None:
        try:
            result, problem = work(), None
        except Exception as error:  # shown to the student as the words of the failure
            result, problem = None, error
        # The window may have closed while the call ran; then nobody is left to tell.
        with suppress(RuntimeError):
            answer.ready.emit(result, problem)

    worker = threading.Thread(target=run, name="flexweek-sync-call", daemon=True)
    pending = (answer, worker)
    # The worker lets go of `answer` as it ends. Were that the last hold, a Qt object would be freed on
    # the worker's thread while the window's thread used it, and the app crashed (1.0.0 gate). This
    # thread holds it until the worker has ended and lets go of it here.
    _IN_FLIGHT.add(pending)

    def release() -> None:
        if worker.is_alive():
            QTimer.singleShot(RELEASE_RETRY_MS, release)
            return
        _IN_FLIGHT.discard(pending)
        if isValid(answer):
            answer.deleteLater()

    def deliver_then_release(result: Any, problem: Exception | None) -> None:
        try:
            deliver(result, problem)
        finally:
            release()

    answer.ready.connect(deliver_then_release, Qt.ConnectionType.QueuedConnection)
    worker.start()


class SyncDot(QWidget):
    """A small filled dot in the status strip. Its colour says the state; its words are the tooltip
    and the accessible name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("syncDot")
        self.setFixedSize(10, 10)
        self.setAccessibleName("Sync status")
        self._state = "off"
        self.hide()

    def show_state(self, state: str) -> None:
        if state == "off":
            self.hide()
            return
        self._state = state
        self.setToolTip(DOT_WORDS[state])
        self.setAccessibleDescription(DOT_WORDS[state])
        self.show()
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_colour(self._state, self.palette()))
        painter.drawEllipse(self.rect())
        painter.end()


def dot_colour(state: str, palette: QPalette) -> QColor:
    """The dot's fill. A problem uses the look's error colour, so it reads in every look."""
    if state == "problem":
        context = current()
        if context is not None:
            return QColor(context.palette["error"])
        return palette.color(QPalette.ColorRole.Text)
    if state == "idle":
        return palette.color(QPalette.ColorRole.Mid)
    if state == "syncing":
        return palette.color(QPalette.ColorRole.Highlight)
    return palette.color(QPalette.ColorRole.Text)


class PairDialog(Dialog):
    """Shows the phone's code and countdown. Closes itself once the phone is paired."""

    paired = Signal()

    def __init__(self, parent: QWidget, sync: SyncService, user_id: int) -> None:
        super().__init__(parent, sheet=True)
        self.setObjectName("pairDialog")
        self.sync = sync
        self.user_id = user_id
        self.closed = False
        self._qr_payload = ""
        layout = self.card_body("Pair a phone")
        intro = QLabel("On the phone, open FlexWeek and type the numbers below.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.code = QLabel("Making a code…")
        self.code.setObjectName("pairCode")
        self.code.setAccessibleName("Pairing code")
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.code)
        self.status = QLabel("")
        self.status.setObjectName("pairStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.problem = QLabel("")
        self.problem.setObjectName("pairProblem")
        self.problem.setWordWrap(True)
        layout.addWidget(self.problem)
        self.again = sheet_button("New code", "outlined", "pairAgain")
        self.again.setEnabled(False)
        self.again.clicked.connect(self._start)
        self.cancel = sheet_button("Cancel", "outlined", "pairCancel")
        self.cancel.clicked.connect(self.reject)
        sheet_footer(layout, self.cancel, self.again)
        self.timer = QTimer(self)
        self.timer.setInterval(PAIR_TICK_MS)
        self.timer.timeout.connect(self._tick)
        self._start()

    def _start(self) -> None:
        self.again.setEnabled(False)
        self.problem.setText("")
        self.code.setText("Making a code…")
        self._qr_payload = ""
        self.status.setText("")
        run_off_ui(self, lambda: self.sync.pair_start(self.user_id), self._made)

    def _made(self, offer: dict | None, problem: Exception | None) -> None:
        if not isValid(self) or self.closed:
            # Cancel came while the code was being made: end the code rather than leave it open.
            if offer is not None:
                run_off_ui(self, self.sync.pair_cancel, lambda _result, _problem: None)
            return
        if problem is not None or offer is None:
            self.code.setText("")
            self.problem.setText(f"Could not make a code: {problem}")
            self.again.setEnabled(True)
            return
        self.code.setText(offer["display_code"])
        self._qr_payload = offer["qr"]
        self.timer.start()
        self._tick()

    def _tick(self) -> None:
        if not isValid(self):
            return
        status = self.sync.pair_status()
        state = status["state"]
        if state == "paired":
            self.timer.stop()
            self.paired.emit()
            self.accept()
            return
        if state == "waiting":
            left = (status["expires_at_ms"] - _now_ms()) // 1000
            self.status.setText(f"{countdown_words(left)}. {tries_words(status['tries_left'])}.")
            return
        self.timer.stop()
        self.status.setText("")
        self.problem.setText(pair_problem(state) or "That code is no longer open. Start a new one.")
        self.again.setEnabled(True)

    def reject(self) -> None:
        self.closed = True
        self.timer.stop()
        super().reject()
        run_off_ui(self, self.sync.pair_cancel, lambda _result, _problem: None)


class RemoveDialog(Dialog):
    """Asks before a phone is removed. The answer is yes or no; nothing else is decided here."""

    def __init__(self, parent: QWidget, name: str) -> None:
        super().__init__(parent, sheet=True)
        self.setObjectName("removeDialog")
        layout = self.card_body(f"Remove {name}?")
        note = QLabel(
            "The phone keeps what it has and gets nothing new from this computer. "
            "To link it again, pair it once more."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        keep = sheet_button("Keep phone", "outlined", "keepPhone")
        keep.clicked.connect(self.reject)
        remove = sheet_button("Remove phone", "danger", "confirmRemove")
        remove.clicked.connect(self.accept)
        sheet_footer(layout, keep, remove)


def _note(words: str) -> QLabel:
    """A line of words in the card that wraps: Settings scrolls down, never sideways."""
    label = QLabel(words)
    label.setWordWrap(True)
    return label


class DevicesPanel(QWidget):
    """The Devices card's body: each linked phone with its last sync and Remove, then Pair a phone and
    Sync now, and the relay sentence. `owner_id` gives the signed-in account's id when asked."""

    def __init__(
        self, host: SyncHost | None, owner_id: Callable[[], int | None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("devicesPanel")
        self.host = host
        self.owner_id = owner_id
        # The sheet now open (pairing or removing), so a test or a focus change can reach it.
        self.dialog: QWidget | None = None
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        self.phones = QVBoxLayout()
        self.phones.setSpacing(6)
        column.addLayout(self.phones)
        self.clock_warning = QLabel("")
        self.clock_warning.setObjectName("clockWarning")
        self.clock_warning.setWordWrap(True)
        self.clock_warning.hide()
        column.addWidget(self.clock_warning)
        self.problem = QLabel("")
        self.problem.setObjectName("devicesProblem")
        self.problem.setWordWrap(True)
        column.addWidget(self.problem)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.pair_button = QPushButton("Pair a phone")
        self.pair_button.setObjectName("pairPhone")
        self.pair_button.setProperty("outline", True)
        self.pair_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.pair_button.clicked.connect(self._pair)
        self.sync_button = QPushButton("Sync now")
        self.sync_button.setObjectName("syncNow")
        self.sync_button.setProperty("outline", True)
        self.sync_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.sync_button.clicked.connect(self._sync_now)
        actions.addWidget(self.pair_button)
        actions.addWidget(self.sync_button)
        actions.addStretch(1)
        column.addLayout(actions)
        relay = QLabel(RELAY_SENTENCE)
        relay.setObjectName("devicesRelay")
        relay.setWordWrap(True)
        column.addWidget(relay)
        if host is not None:
            host.started.connect(self._service_started)
        self.refresh()

    def refresh(self) -> None:
        if not isValid(self):
            return
        while self.phones.count():
            item = self.phones.takeAt(0)
            if item.widget() is not None:
                _discard(item.widget())
        if self.host is None:
            self._disable(NO_SYNC_WORDS)
            return
        self._set_buttons()
        service = self.host.service
        if service is None:
            # No phone was linked at launch, so there is nothing to list until one is paired.
            self.phones.addWidget(_note(NO_PHONE_WORDS))
            return
        try:
            phones = live_phones(service, self.owner_id())
        except SyncError as error:
            self.phones.addWidget(_note(f"Could not read your phones: {error}"))
            return
        if not phones:
            self.phones.addWidget(_note(NO_PHONE_WORDS))
            return
        now_ms = _now_ms()
        for phone in phones:
            row = QHBoxLayout()
            row.setSpacing(12)
            name = QLabel(phone["name"])
            name.setObjectName("phoneName")
            seen = QLabel(seen_words(phone["last_seen"], now_ms))
            seen.setObjectName("phoneSeen")
            remove = QPushButton("Remove")
            remove.setObjectName("removePhone")
            remove.setProperty("outline", True)
            remove.setProperty("device_id", phone["device_id"])
            remove.clicked.connect(lambda _checked=False, p=phone: self._remove(p))
            row.addWidget(name)
            row.addWidget(seen, 1)
            row.addWidget(remove)
            holder = QWidget()
            holder.setLayout(row)
            self.phones.addWidget(holder)

    def _set_buttons(self) -> None:
        # Pair is off while the service is starting, so a second press cannot start a second code.
        self.pair_button.setEnabled(self.owner_id() is not None and not self.host.starting)
        self.sync_button.setEnabled(self.host.service is not None)

    def _service_started(self, _service: object) -> None:
        if not isValid(self):
            return
        self.refresh()

    def _disable(self, words: str) -> None:
        self.pair_button.setEnabled(False)
        self.sync_button.setEnabled(False)
        self.phones.addWidget(_note(words))

    def _pair(self) -> None:
        user_id = self.owner_id()
        if self.host is None or user_id is None:
            return
        self.pair_button.setEnabled(False)
        self.host.ensure(lambda service: self._pairing(service, user_id))

    def _pairing(self, service: SyncService | None, user_id: int) -> None:
        if not isValid(self):
            return
        self._set_buttons()
        if service is None:
            self.problem.setText(NO_SYNC_WORDS)
            return
        dialog = PairDialog(self, service, user_id)
        dialog.paired.connect(self.refresh)
        self._open_sheet(dialog)

    def _remove(self, phone: dict) -> None:
        user_id = self.owner_id()
        service = self.host.service if self.host is not None else None
        if service is None or user_id is None:
            return
        dialog = RemoveDialog(self, phone["name"])

        def gone(answer: Any, problem: Exception | None) -> None:
            if not isValid(self):
                return
            if problem is not None:
                self.problem.setText(f"Could not remove {phone['name']}: {problem}")
            self.refresh()

        def confirmed(result: int) -> None:
            if not isValid(self) or result != 1:
                return
            run_off_ui(self, lambda: service.unlink(user_id, phone["device_id"], True), gone)

        dialog.finished.connect(confirmed)
        self._open_sheet(dialog)

    def _forget_sheet(self, dialog: Dialog) -> None:
        if not isValid(self):
            return
        if self.dialog is dialog:
            self.dialog = None

    def _open_sheet(self, dialog: Dialog) -> None:
        if self.dialog is not None:
            _discard(self.dialog)
        self.dialog = dialog
        dialog.finished.connect(lambda _result: self._forget_sheet(dialog))
        dialog.open()

    def _sync_now(self) -> None:
        service = self.host.service if self.host is not None else None
        if service is None:
            return
        self.sync_button.setEnabled(False)
        run_off_ui(self, lambda: service.sync_all(SYNC_DEADLINE_MS), self._synced)

    def _synced(self, rows: list | None, problem: Exception | None) -> None:
        if not isValid(self):
            return
        self.sync_button.setEnabled(True)
        if problem is not None:
            self.problem.setText(f"Sync failed: {problem}")
            return
        clock_skewed = sum(
            row[1].get("clock_skewed", 0)
            for row in rows or []
            if row[1] is not None and row[2] is None
        )
        self.clock_warning.setText(clock_warning_words(clock_skewed))
        self.clock_warning.setVisible(clock_skewed > 0)
        failed = [row for row in rows or [] if row[2] is not None]
        self.problem.setText(UNREACHABLE_WORDS if failed else "")
        self.refresh()


def _discard(widget: QWidget) -> None:
    # Out of the parent's children at once, so a search for a label does not find a removed one.
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


def _now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)
