"""Asynchronous access to FlexWeek's saved data. Each request is answered by the Rust service
(`flexweek_engine.service_answer`) on a worker thread, in this process, with no server and no network
port; the answer comes back on the window's thread on a later turn of its event loop."""

from __future__ import annotations

import contextlib
import json
import logging
import re
import secrets
import weakref
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from shiboken6 import isValid

from backend import clock as wall_clock

REQUEST_TIMEOUT_MS = 30_000
# Requests answered at once. Each waits on the database or hashes a password without holding Python, so
# a Plan or a sign-in does not hold up the reads behind it.
WORKERS = 4
# How often a gone client's courier looks again for answers still being made before it is freed.
RELEASE_RETRY_MS = 200
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
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
SIGN_IN_WHY = "FlexWeek doesn't say which, so no one can find out who has an account."
SIGN_IN_NO_USERNAME = "Type your username."
SIGN_IN_NO_PASSWORD = "Type your password."
SIGN_IN_BAD_USERNAME = (
    "No FlexWeek username looks like that. Usernames are 3–32 letters, numbers or underscores."
)
SIGN_IN_SHORT_PASSWORD = "That isn't your password. FlexWeek passwords have at least 12 characters."
SIGN_UP_NO_USERNAME = "Choose a username."
SIGN_UP_NO_PASSWORD = "Choose a password with at least 12 characters."
SIGN_UP_SHORT_PASSWORD = "Add {n} more {unit}. Passwords need at least 12."
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


@dataclass(frozen=True)
class Answer:
    """What the service answered: the status, the body as JSON text (empty for none), and whether the
    request started a session (`token`), ended it, or kept it."""

    status: int
    body: bytes
    session: str = "kept"
    token: str = ""


def ask(
    database: str,
    method: str,
    path: str,
    body: str,
    token: str,
    account_id: int | None,
    seconds: int,
    now: str,
    restore_token: str,
) -> Answer:
    """One request answered by the service. Runs on a worker thread, so it touches no Qt object."""
    try:
        status, text, session, new_token = flexweek_engine.service_answer(
            database,
            method,
            path,
            body,
            token,
            str(account_id) if account_id is not None else None,
            seconds,
            now,
            restore_token,
        )
    except Exception as error:  # an engine failure is a server error to the window, as it was
        logger.error("The service failed to answer a request: %s", type(error).__name__)
        return Answer(500, b"")
    return Answer(status, (text or "").encode(), session, new_token)


def _api_path(path: str) -> None:
    parsed = urlsplit(path)
    decoded = unquote(parsed.path)
    if (
        not path.startswith("/api/")
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or "#" in path
        or "\\" in decoded
        or "//" in decoded
        or any(part in {".", ".."} for part in decoded.split("/"))
        or any(ord(char) < 33 or ord(char) == 127 for char in path)
        or not decoded.startswith("/api/")
    ):
        raise ValueError("Only relative /api/ requests are allowed.")


def _field_error(detail: object, names: tuple[str, ...], message: str) -> str | None:
    items = detail if isinstance(detail, list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        loc = [str(part).lower() for part in (item.get("loc") or [])]
        if any(name in loc for name in names):
            return message
    return None


def _password_error(detail: object) -> str | None:
    return _field_error(detail, ("password", "new_password", "current_password"), PASSWORD_LENGTH_HINT)


def _username_error(detail: object) -> str | None:
    return _field_error(detail, ("username",), USERNAME_ERROR)


def _error(status: int, detail: object = None) -> ApiError:
    if status == 401 and detail == "Incorrect password":
        return ApiError(status, WRONG_PASSWORD)
    if status == 401 and detail == "Incorrect username or password":
        return ApiError(status, SIGN_IN_WRONG)
    if status == 409 and detail == "Username unavailable":
        return ApiError(status, USERNAME_TAKEN)
    if status == 401 and detail == "Incorrect username or recovery code":
        return ApiError(status, "Wrong username or recovery code. Each code works once; try another one.")
    if status == 401 and detail == SESSION_ENDED:
        return ApiError(status, SESSION_ENDED)
    if status == 422:
        named = _password_error(detail) or _username_error(detail)
        if named:
            return ApiError(status, named)
    messages = {
        0: "Could not reach FlexWeek. Your changes may not have been saved. Try again.",
        401: SIGN_IN_AGAIN,
        403: "This request was refused. Restart FlexWeek and try again.",
        404: "This item is no longer available. Reload and try again.",
        409: "The saved data changed or that name is already in use. Reload and try again.",
        413: "This request is too large. Reduce its size and try again.",
        422: "Check the required fields, dates, times and lengths, then try again.",
        429: TOO_MANY_TRIES,
        503: "Storage is unavailable. Keep your changes and try again shortly.",
    }
    return ApiError(status, messages.get(status, "FlexWeek could not complete this request. Try again."))


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


def auth_error(error: ApiError, *, creating: bool) -> ApiError:
    """The words for a sign-in or sign-up that failed on the way. The general ones speak of changes
    that may not have been saved, which a sign-in never has."""
    then = "create your account" if creating else "sign in"
    if error.status == 0:
        return ApiError(0, f"FlexWeek can't reach its server. Close FlexWeek, open it again, then {then}.")
    if error.status == 503:
        return ApiError(503, f"FlexWeek can't open its saved data right now. Wait a minute, then {then}.")
    return error


class _Courier(QObject):
    """Carries answers from the workers to one client. It has no parent: freed with its client, it would
    go while a worker was still sending on it (devices.py met that crash). A gone client's courier is
    kept in _RETIRED and freed on the window's thread once no answer for it is being made."""

    # (request number, Answer); queued, so it lands on the window's thread.
    answered = Signal(int, object)


# The workers every client shares, made when the first request is sent.
_POOL: ThreadPoolExecutor | None = None
# Couriers whose client is gone, each with the requests still being answered for it.
_RETIRED: list[tuple[_Courier, set[Future]]] = []


def _workers() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="flexweek-request")
    return _POOL


def stop_workers() -> None:
    """At quit: drop requests not started and wait for the ones being answered, so none writes after the
    app has let go of its files."""
    global _POOL
    if _POOL is not None:
        _POOL.shutdown(wait=True, cancel_futures=True)
        _POOL = None


def _retire(courier: _Courier, running: set[Future]) -> None:
    """Free a gone client's courier on this (the window's) thread once nothing is answering for it."""
    kept = (courier, running)
    _RETIRED.append(kept)

    def release() -> None:
        if running:
            QTimer.singleShot(RELEASE_RETRY_MS, release)
            return
        _RETIRED.remove(kept)
        if isValid(courier):
            courier.deleteLater()

    release()


class NativeClient(QObject):
    expired = Signal()

    def __init__(self, database: str | Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.database = str(database)
        self.account: dict | None = None
        self.epoch = 0
        self._token = ""
        self._number = 0
        # Requests sent and not yet answered: what to do with each answer, by number.
        self._waiting: dict[int, Callable[[Answer], None]] = {}
        # Requests a worker is answering or will answer; each leaves the set when its answer is made.
        self._running: set[Future] = set()
        courier, running = _Courier(), self._running
        self._courier = courier
        courier.answered.connect(self._land, Qt.ConnectionType.QueuedConnection)
        self.destroyed.connect(lambda *_: _retire(courier, running))

    def _check_thread(self) -> None:
        if QThread.currentThread() != self.thread():
            raise RuntimeError("The native API client must be used on its Qt thread.")

    def _rotate(self) -> None:
        """A new account epoch: every answer still on its way is dropped when it lands. Its timer runs
        out on its own, at most REQUEST_TIMEOUT_MS later."""
        self.epoch += 1

    def set_account(self, identity: dict) -> None:
        self._check_thread()
        if (
            type(identity.get("id")) is not int
            or identity["id"] <= 0
            or not isinstance(identity.get("username"), str)
            or not identity["username"]
        ):
            raise ValueError("An account needs a valid id and username.")
        self.account = {"id": identity["id"], "username": identity["username"]}
        self._rotate()

    def reset(self) -> None:
        self._check_thread()
        self.account = None
        self._token = ""
        self._rotate()

    def session_token(self) -> str | None:
        return self._token or None

    def adopt_session(self, token: str) -> None:
        """A session kept from an earlier launch; the next request says whether it still works."""
        self._check_thread()
        self.account = None
        self._rotate()
        self._token = token

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
        _api_path(path)
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError("Unsupported API request method.")
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("API request bodies must be JSON objects.")
        encoded = json.dumps(payload, allow_nan=False) if payload is not None else ""
        account_id = self.account["id"] if self.account is not None else None
        epoch = self.epoch

        def finish(answer: Answer, reached: bool) -> None:
            if epoch != self.epoch:
                return
            status, body = answer.status, answer.body
            if answer.session == "started":
                self._token = answer.token
            elif answer.session == "ended":
                self._token = ""
            result: object = None
            if len(body) <= MAX_RESPONSE_BYTES:
                with contextlib.suppress(ValueError, UnicodeDecodeError):
                    result = json.loads(body) if body else {}
            detail = result.get("detail") if isinstance(result, dict) else None
            if not 200 <= status < 300 or not reached:
                self._notify_error(on_error, _error(status, detail))
                expired = (
                    status == 401
                    and account_id is not None
                    and detail
                    not in {
                        "Incorrect password",
                        "Incorrect username or password",
                        "Incorrect username or recovery code",
                    }
                    and epoch == self.epoch
                )
                if expired:
                    self.expired.emit()
                return
            if not isinstance(result, dict) or (not body and status != 204):
                self._notify_error(on_error, ApiError(status, "FlexWeek returned an unreadable response."))
                return
            try:
                on_success(result)
            except Exception:
                logger.error("A native request result handler failed.")
                self._notify_error(on_error, ApiError(status, "FlexWeek could not display this response."))

        self._send(method, path, encoded, account_id, finish)

    def _clock(self) -> tuple[int, str, str]:
        """The app's clock as the request is sent, and the name a restore point it makes would take."""
        return (
            int(wall_clock.seconds()),
            wall_clock.now().strftime("%Y-%m-%dT%H:%M"),
            secrets.token_hex(8),
        )

    def _send(
        self,
        method: str,
        path: str,
        encoded: str,
        account_id: int | None,
        finish: Callable[[Answer, bool], None],
    ) -> None:
        """Ask the service on a worker; `finish` gets the answer and whether one came at all (one that
        takes longer than REQUEST_TIMEOUT_MS counts as none, and is dropped when it lands)."""
        self._number += 1
        number = self._number
        timer = QTimer(self)
        timer.setSingleShot(True)

        def landed(answer: Answer, reached: bool = True) -> None:
            timer.stop()
            timer.deleteLater()
            finish(answer, reached)

        def timed_out() -> None:
            if self._waiting.pop(number, None) is not None:
                landed(Answer(0, b""), reached=False)

        self._waiting[number] = landed
        timer.timeout.connect(timed_out)
        timer.start(REQUEST_TIMEOUT_MS)
        seconds, now, restore = self._clock()
        arguments = (self.database, method, path, encoded, self._token, account_id, seconds, now, restore)
        # Only a weak reference rides with the work: the worker's own hold on the courier is taken just
        # to send and let go before the work ends, while the client or _RETIRED still holds it, so the
        # last hold is never the worker's and the courier is never freed on its thread.
        courier = weakref.ref(self._courier)

        def work() -> None:
            answer = ask(*arguments)
            target = courier()
            try:
                # The window may have closed while the service answered; then no one is left to tell.
                if target is not None:
                    with contextlib.suppress(RuntimeError):
                        target.answered.emit(number, answer)
            finally:
                target = None

        future = _workers().submit(work)
        self._running.add(future)
        future.add_done_callback(self._running.discard)

    def _land(self, number: int, answer: Answer) -> None:
        landed = self._waiting.pop(number, None)
        if landed is not None:
            landed(answer)
