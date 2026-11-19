"""Phones linked to this computer: the sync service's start-up, its calls off the window thread, and the
sync status dot in the week's status strip."""

from __future__ import annotations

import socket
import sqlite3
import sys
import threading
import weakref
from collections.abc import Callable
from contextlib import closing, suppress
from pathlib import Path
from typing import Any

from flexweek_engine import SyncError, SyncService  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from shiboken6 import isValid

SYNC_SCAN_MS = 1000
# The whole of one "Sync now" call. flexweek-sync's own default is 45 s.
SYNC_DEADLINE_MS = 45_000
NO_SYNC_WORDS = "Syncing isn't available on this computer right now. Your week is still saved here."


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


def begin_pairing(
    owner: QObject,
    service: SyncService,
    user_id: int,
    done: Callable[[Any, Exception | None], None],
) -> None:
    """Ask for a pairing code off the UI thread. `owner` is who the answer goes back to."""
    run_off_ui(owner, lambda: service.pair_start(user_id), done)


def end_pairing(owner: QObject, service: SyncService, done: Callable[[Any, Exception | None], None]) -> None:
    """Close the open pairing code."""
    run_off_ui(owner, service.pair_cancel, done)


def unlink_phone(
    owner: QObject,
    service: SyncService,
    user_id: int,
    device_id: str,
    done: Callable[[Any, Exception | None], None],
) -> None:
    """Remove a linked phone. The phone keeps what it already has."""
    run_off_ui(owner, lambda: service.unlink(user_id, device_id, True), done)


def sync_linked_phones(
    owner: QObject, service: SyncService, done: Callable[[Any, Exception | None], None]
) -> None:
    """Sync every linked phone, with the same deadline Sync now already uses."""
    run_off_ui(owner, lambda: service.sync_all(SYNC_DEADLINE_MS), done)




# The error colour of the look in force, set by the window each time it dresses itself.
_error_colour: str | None = None


def set_error_colour(colour: str | None) -> None:
    global _error_colour
    _error_colour = colour


