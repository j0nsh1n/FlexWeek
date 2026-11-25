"""Access to FlexWeek's saved data. The session in Rust (`flexweek_engine.NativeCore`,
engine/app/src/session) sends each request to the service on its own workers, in this process, with no
server and no network port; its answer is taken back on the window's thread on a later turn of its event
loop and handed to the request's callbacks here."""

from __future__ import annotations

import itertools
import json
import logging
import re
import secrets
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from shiboken6 import isValid

from backend import clock as wall_clock

PASSWORD_LENGTH_HINT = "At least 12 characters."
USERNAME_HINT = "3 to 32 letters, numbers or underscores."
USERNAME_ERROR = "Use 3 to 32 letters, numbers or underscores, with no spaces."
WRONG_PASSWORD = "Wrong password. Try again."
TYPE_RECOVERY_CODE = "Type a recovery code."
TOO_MANY_TRIES = "Too many tries. Wait 5 minutes, then try again."
# Sign-in and sign-up say which thing is wrong wherever FlexWeek can tell. The server answers a wrong
# password and an unknown username alike on purpose; the sign-in card's link says why.
SIGN_IN_WRONG = "Wrong username or password. Try again, or choose Forgot password."
SIGN_IN_WHY_LINK = "Why doesn't it say which?"
SIGN_IN_WHY = "FlexWeek doesn't say which one is wrong, so no one can use it to find out who has an account."
SIGN_IN_NO_USERNAME = "Type your username."
SIGN_IN_NO_PASSWORD = "Type your password."
SIGN_IN_BAD_USERNAME = (
    "No FlexWeek username looks like that. Usernames are 3–32 letters, numbers or underscores."
)
SIGN_IN_SHORT_PASSWORD = "Passwords have at least 12 characters. Try again, or choose Forgot password."
SIGN_UP_NO_USERNAME = "Choose a username."
SIGN_UP_NO_PASSWORD = "Choose a password with at least 12 characters."
SIGN_UP_SHORT_PASSWORD = "Add {n} more {unit}. Passwords need at least 12 characters."
SIGN_UP_LONG_PASSWORD = "Use 128 characters or fewer."
USERNAME_TAKEN = "That username is taken. Try another."
# Said when a session ends; about no one field, though its words name two.
SIGN_IN_AGAIN = "Please sign in again, or check your username and password."
SESSION_ENDED = "Your session ended. Sign in again."
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiError:
    status: int
    message: str


def _error(status: int, detail: object = None) -> ApiError:
    """The words for a failed request, from the session (engine/app/src/session/words.rs)."""
    return ApiError(status, flexweek_engine.session_error_words(status, json.dumps(detail, default=str)))


def _username_ok(name: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_]{3,32}", name) is not None


def sign_in_problem(name: str, password: str) -> str:
    """What is wrong before asking the server, which could only say "check the required fields"."""
    if not name:
        return SIGN_IN_NO_USERNAME
    if not password:
        return SIGN_IN_NO_PASSWORD
    if not _username_ok(name):
        return SIGN_IN_BAD_USERNAME
    if len(password) < 12:
        return SIGN_IN_SHORT_PASSWORD
    return ""


def sign_up_problem(name: str, password: str) -> str:
    if not name:
        return SIGN_UP_NO_USERNAME
    if not _username_ok(name):
        return USERNAME_ERROR
    if not password:
        return SIGN_UP_NO_PASSWORD
    if len(password) > 128:
        return SIGN_UP_LONG_PASSWORD
    if len(password) < 12:
        return short_password_needed(12 - len(password))
    return ""


def short_password_needed(n: int) -> str:
    unit = "character" if n == 1 else "characters"
    return SIGN_UP_SHORT_PASSWORD.format(n=n, unit=unit)


class _Host:
    """What the session asks of the computer (engine/py/src/session.rs), on the window's thread and on its
    workers: a clock that only moves forward, the app's clock (which tests set), the name of a restore point
    a request makes, and randomness."""

    def steady_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def request_clock(self) -> tuple[int, str]:
        return int(wall_clock.seconds()), wall_clock.now().strftime("%Y-%m-%dT%H:%M")

    def restore_token(self) -> str:
        return secrets.token_hex(8)

    def entropy(self) -> object:
        return secrets


HOST = _Host()


class _Courier(QObject):
    """Carries "an answer is ready" from the session's workers to the window's thread. One for the whole
    program, never freed, so a worker never holds the last reference to a Qt object."""

    woke = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.woke.connect(self.deliver, Qt.ConnectionType.QueuedConnection)

    @Slot(int)
    def deliver(self, key: int) -> None:
        client = _CLIENTS.get(key)
        if client is not None and isValid(client):
            client._drain()


_COURIER: _Courier | None = None
# Each client by the number its session wakes it with.
_CLIENTS: weakref.WeakValueDictionary[int, NativeClient] = weakref.WeakValueDictionary()
_KEYS = itertools.count(1)


def _wake(key: int) -> None:
    """Called by the session on a worker's thread: only posts to the window's thread."""
    courier = _COURIER
    if courier is not None:
        courier.woke.emit(key)


def stop_workers() -> None:
    """At quit: drop requests not started and wait for the ones being answered, so none writes after the
    app has let go of its files."""
    flexweek_engine.stop_session_workers()


class NativeClient(QObject):
    """The window's side of the session: sends requests, keeps what to do with each answer by its number,
    and takes the session's events when a worker wakes it or the next request reaches its 30-second limit.
    `inline` answers each request as it is sent (the desktop tests' light app); the answer still comes on a
    later turn of the window's loop."""

    expired = Signal()
    # A flow the session ran (signing in, up or out) finished: its event (engine/app/src/session/account.rs).
    told = Signal(dict)

    def __init__(self, database: str | Path, parent: QObject | None = None, *, inline: bool = False) -> None:
        super().__init__(parent)
        global _COURIER
        if _COURIER is None:
            _COURIER = _Courier()
        self.database = str(database)
        key = next(_KEYS)
        _CLIENTS[key] = self
        self._core = flexweek_engine.NativeCore(self.database, HOST, lambda: _wake(key), inline)
        # Requests sent and not yet answered: what to do with each answer, by number.
        self._waiting: dict[int, tuple[Callable[[dict], None], Callable[[ApiError], None]]] = {}
        self._limit = QTimer(self)
        self._limit.setSingleShot(True)
        self._limit.setTimerType(Qt.TimerType.PreciseTimer)
        self._limit.timeout.connect(self._drain)

    def _check_thread(self) -> None:
        if QThread.currentThread() != self.thread():
            raise RuntimeError("The native API client must be used on its Qt thread.")

    def _send(self, command: dict) -> dict:
        answer = json.loads(self._core.send(json.dumps(command, allow_nan=False)))
        if not answer.get("ok"):
            raise ValueError(answer.get("error", "The session refused the command."))
        return answer

    def _frame(self) -> dict:
        return json.loads(self._core.view("frame"))

    def command(self, command: dict) -> dict:
        """One command to the session (engine/app/src/session/mod.rs); a refusal raises ValueError. A command
        may send a request of the session's own (signing in), so the limit's timer is set again."""
        self._check_thread()
        answer = self._send(command)
        self._arm()
        return answer

    def view(self, name: str) -> dict:
        """One of the session's views (engine/app/src/session/mod.rs)."""
        return json.loads(self._core.view(name))

    @property
    def account(self) -> dict | None:
        return self._frame()["account"]

    @property
    def epoch(self) -> int:
        """Rises on every sign-in, sign-out and kept session taken up; an answer to a request sent in an
        earlier one is dropped."""
        return self._frame()["epoch"]

    def set_account(self, identity: dict) -> None:
        self._check_thread()
        if (
            type(identity.get("id")) is not int
            or identity["id"] <= 0
            or not isinstance(identity.get("username"), str)
            or not identity["username"]
        ):
            raise ValueError("An account needs a valid id and username.")
        self._send({"cmd": "set_account", "id": identity["id"], "username": identity["username"]})

    def reset(self) -> None:
        self._check_thread()
        self._send({"cmd": "reset"})

    def session_token(self) -> str | None:
        return self._frame()["token"]

    def adopt_session(self, token: str) -> None:
        """A session kept from an earlier launch; the next request says whether it still works."""
        self._check_thread()
        self._send({"cmd": "adopt_session", "token": token})

    @staticmethod
    def _notify_error(callback: Callable[[ApiError], None], error: ApiError) -> None:
        try:
            callback(error)
        except Exception:
            logger.error("A native request error handler failed.")

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None,
        on_success: Callable[[dict], None],
        on_error: Callable[[ApiError], None],
    ) -> None:
        self._check_thread()
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("API request bodies must be JSON objects.")
        sent = self._send({"cmd": "request", "method": method, "path": path, "body": payload})
        self._waiting[sent["number"]] = (on_success, on_error)
        self._arm()

    def _arm(self) -> None:
        """Look again when the next request reaches its limit: one that never comes back wakes no one."""
        deadline = self._frame()["next_deadline"]
        if deadline is None:
            self._limit.stop()
        else:
            self._limit.start(max(0, deadline - HOST.steady_ms()))

    def _drain(self) -> None:
        """Takes the session's next answer: each worker's wake, or the limit's timer, brings one. One per
        turn of the window's loop, as each answer landed on its own before, so what the window queues while
        handling one runs before the next is read; with it, the end of the session if that answer said so."""
        while isValid(self):
            event = json.loads(self._core.take_event())
            if event is None:
                break
            if event["kind"] == "expired":
                self.expired.emit()
                continue
            if event["kind"] in {"answer", "dropped"}:
                self._hand(event)
            else:
                self.told.emit(event)
            if isValid(self) and self._core.take_expiry():
                self.expired.emit()
            break
        if isValid(self):
            self._arm()

    def _hand(self, event: dict) -> None:
        """An answer to its request's callbacks; one that no longer counts goes to no one."""
        callbacks = self._waiting.pop(event["number"], None)
        if callbacks is None or event["kind"] == "dropped":
            return
        on_success, on_error = callbacks
        if not event["ok"]:
            self._notify_error(on_error, ApiError(event["status"], event["message"]))
            return
        try:
            on_success(event["body"])
        except Exception:
            logger.error("A native request result handler failed.")
            self._notify_error(
                on_error, ApiError(event["status"], "FlexWeek could not display this response.")
            )
