"""The desktop's requests answered by Rust (flexweek_service::desk_requests) as the local server answers
them: one scripted run of every route the window uses, with the refusals around each, sent to the FastAPI
app and to `service_answer` on two copies of one store, gives the same status, body and session change at
every step. It goes with the server in P2, once the window no longer has a server to ask."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient

from backend import clock as wall_clock
from backend.app import create_app
from backend.storage import initialize
from backend.tests.account_support import (
    PASSWORD,
    REPLACEMENT,
    THIS_WEEK,
    WEEK,
    assignment,
    flex,
    preferences,
    school,
)
from backend.tests.fake_clock import CLOCK

ORIGIN = "http://127.0.0.1:8941"
SENT = {"X-FlexWeek-Request": "1", "Origin": ORIGIN, "Content-Type": "application/json"}
# The POST routes that name a restore point the request may make, as the server draws one for each (and
# /api/restore-points/{id}/restore).
DRAWS_A_RESTORE_TOKEN = ("/api/changes", "/api/account-import", "/api/restore-points")


@pytest.fixture()
def same_randomness(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """`secrets` made repeatable: each (function, size) draws its own numbered stream, so both sides draw
    the same tokens, salts and codes. Calling the result starts every stream again."""
    counts: dict[tuple[str, int], int] = {}

    def drawn(name: str, size: int) -> bytes:
        count = counts.get((name, size), 0)
        counts[(name, size)] = count + 1
        return hashlib.sha256(f"{name}:{size}:{count}".encode()).digest()[:size]

    monkeypatch.setattr(secrets, "token_bytes", lambda size=32: drawn("bytes", size))
    monkeypatch.setattr(secrets, "token_hex", lambda size=32: drawn("hex", size).hex())
    monkeypatch.setattr(
        secrets,
        "token_urlsafe",
        lambda size=32: __import__("base64").urlsafe_b64encode(drawn("url", size)).rstrip(b"=").decode(),
    )
    return counts.clear


@dataclass
class Reply:
    status: int
    body: object
    # "kept", "ended" or the new token.
    session: str


class Server:
    def __init__(self, database: Path) -> None:
        self._client = TestClient(create_app(database=database, origin=ORIGIN), base_url=ORIGIN)
        self._client.__enter__()
        self.token = ""

    def send(self, method: str, path: str, body: str, account: int | None) -> Reply:
        headers = dict(SENT)
        if self.token:
            headers["Cookie"] = f"flexweek_session={self.token}"
        if account is not None:
            headers["X-FlexWeek-Account"] = str(account)
        response = self._client.request(method, path, content=body.encode() or None, headers=headers)
        self._client.cookies.clear()
        session = "kept"
        for raw in response.headers.get_list("set-cookie"):
            morsel = SimpleCookie(raw)["flexweek_session"]
            ended = morsel["max-age"] == "0" or not morsel.value.strip('"')
            session = "ended" if ended else morsel.value
        if session == "ended":
            self.token = ""
        elif session != "kept":
            self.token = session
        try:
            parsed: object = response.json() if response.content else None
        except ValueError:
            parsed = response.text
        return Reply(response.status_code, parsed, session)

    def close(self) -> None:
        self._client.__exit__(None, None, None)


class Rust:
    def __init__(self, database: Path) -> None:
        initialize(database)
        self._path = str(database)
        self.token = ""

    def send(self, method: str, path: str, body: str, account: int | None) -> Reply:
        route = path.split("?")[0]
        draws = method == "POST" and (route in DRAWS_A_RESTORE_TOKEN or route.endswith("/restore"))
        restore = secrets.token_hex(8) if draws else ""
        status, text, session, token = flexweek_engine.service_answer(
            self._path,
            method,
            path,
            body,
            self.token,
            str(account) if account is not None else None,
            int(wall_clock.seconds()),
            wall_clock.now().strftime("%Y-%m-%dT%H:%M"),
            restore,
        )
        if session == "started":
            self.token = token
        elif session == "ended":
            self.token = ""
        reply_session = token if session == "started" else session
        parsed: object = json.loads(text) if text is not None else None
        return Reply(status, parsed, reply_session)


# One step: method, path, and the body (a dict, raw text, or a function of the answers so far).
Body = dict | str | None | Callable[[list[Reply]], dict | str]
STEPS: list[tuple[str, str | Callable[[list[Reply]], str], Body]] = []


def step(method: str, path: str | Callable[[list[Reply]], str], body: Body = None) -> None:
    STEPS.append((method, path, body))


def last(index: int, *keys: str | int) -> Callable[[list[Reply]], object]:
    def read(replies: list[Reply]) -> object:
        value: object = replies[index].body
        for key in keys:
            value = value[key]  # type: ignore[index]
        return value

    return read


# Before any account.
step("GET", "/api/health")
step("GET", "/api/auth/me")
step("GET", "/api/week")
step("GET", "/api/nothing-here")
step("PATCH", "/api/week", {})
step("POST", "/api/auth/login", {"username": "nobody", "password": PASSWORD})
step("POST", "/api/auth/register", {"username": "ab", "password": PASSWORD})
step("POST", "/api/auth/register", {"username": "ana", "password": "short"})
step("POST", "/api/auth/register", {"username": "ana", "password": PASSWORD, "extra": 1})
step("POST", "/api/auth/register", {"username": "ana", "password": PASSWORD, "keep": "yes"})
step("POST", "/api/auth/register", {"username": 7, "password": PASSWORD})
step("POST", "/api/auth/register", "[1, 2]")
step("POST", "/api/auth/register", "not json")
step("POST", "/api/auth/register", "")
step("POST", "/api/auth/register", {"username": "Ana_1", "password": PASSWORD, "keep": True})
SIGNED_UP = len(STEPS) - 1
step("POST", "/api/auth/register", {"username": "ana_1", "password": PASSWORD})
step("GET", "/api/auth/me")
step("GET", "/api/auth/recovery-status")
# Reads.
step("GET", "/api/week")
step("GET", f"/api/week?week_start={WEEK}")
step("GET", "/api/week?week_start=2026-09-17")
step("GET", "/api/week?week_start=nonsense")
step("GET", "/api/weeks")
step("GET", "/api/day")
step("GET", "/api/day?date=2026-11-05")
step("GET", "/api/day?date=2026-13-01")
step("GET", "/api/month")
step("GET", "/api/month?month=2026-11")
step("GET", "/api/month?month=2026-11&first_day=6")
step("GET", "/api/month?month=2026-11&first_day=7")
step("GET", "/api/month?month=2026-11&first_day=x")
step("GET", "/api/month?month=1999-12")
step("GET", "/api/assignments")
step("GET", f"/api/assignments?week_start={THIS_WEEK}")
step("GET", f"/api/assignments?week_start={THIS_WEEK}&include_completed=true")
step("GET", f"/api/assignments?week_start={THIS_WEEK}&include_completed=Yes")
step("GET", f"/api/assignments?week_start={THIS_WEEK}&include_completed=maybe")
step("GET", "/api/preferences")
step("GET", "/api/routines")
step("GET", "/api/restore-points")
step("GET", "/api/storage-info")
step("GET", "/api/timer-presets")
step("GET", "/api/reminder-limits")
# Saves.
step("PUT", "/api/preferences", preferences("slate"))
step("PUT", "/api/preferences", {"theme": "purple"})
step("PUT", "/api/preferences", "[]")
step("PUT", "/api/week", {"week_start": WEEK, "blocks": [school()], "revision": 0})
step("PUT", "/api/week", {"week_start": WEEK, "blocks": [school()], "revision": 0})
step("PUT", "/api/week", {"week_start": WEEK, "blocks": [school(), school()], "revision": 1})
step("PUT", "/api/week", "nope")
step("GET", f"/api/week?week_start={WEEK}")
step("PUT", "/api/assignments/hw-essay", assignment())
step("PUT", "/api/assignments/hw-essay", assignment())
step("PUT", "/api/assignments/hw%20two", assignment(id="hw two", title="Two"))
step("POST", "/api/assignments/hw-essay/spread", {"session_min": 60, "from_date": WEEK})
step("POST", "/api/assignments/hw-essay/spread", {"week_start": WEEK})
step("POST", "/api/assignments/missing/spread", {"session_min": 60, "from_date": WEEK})
step("GET", f"/api/assignments?week_start={WEEK}")
step("DELETE", "/api/assignments/hw%20two")
step("DELETE", "/api/assignments/hw%20two?revision=abc")
step("DELETE", "/api/assignments/hw%20two?revision=99999999999999999999999")
step("DELETE", "/api/assignments/hw%20two?revision=1")
step("DELETE", "/api/assignments/hw%20two?revision=1")
step(
    "POST",
    "/api/changes",
    {
        "weeks": [{"week_start": THIS_WEEK, "blocks": [flex("hw-1")], "revision": 0}],
        "assignments": [],
        "operation_id": "op-1",
    },
)
step(
    "POST",
    "/api/changes",
    {
        "weeks": [{"week_start": THIS_WEEK, "blocks": [flex("hw-1")], "revision": 0}],
        "assignments": [],
        "operation_id": "op-1",
    },
)
step("POST", "/api/changes", {"weeks": "no"})
step("POST", "/api/repeat-edits", {"repeats": []})
step("POST", "/api/repeat-edits", {"week_start": WEEK, "edits": []})
step("POST", "/api/solve", {"blocks": [school(), flex("hw-2")], "week_start": WEEK, "now_floor": None})
step("POST", "/api/solve", {"blocks": "no", "week_start": WEEK})
step(
    "POST",
    "/api/timer-split-preview",
    {
        "duration_min": 120,
        "timer_work_min": 30,
        "timer_break_min": 15,
        "timer_long_break_min": 30,
        "timer_long_break_every": 4,
    },
)
step("POST", "/api/timer-split-preview", {"duration_min": "x"})
step("PUT", "/api/routines/r1", {"id": "r1", "name": "Morning", "blocks": [], "revision": 0})
step("PUT", "/api/routines/r1", {"id": "r2", "name": "Morning", "blocks": [], "revision": 0})
step("GET", "/api/routines")
step("DELETE", "/api/routines/r1")
step("DELETE", "/api/routines/r1?revision=1&operation_id=del-1")
step("DELETE", "/api/routines/r1?revision=1&operation_id=del-1")
# Restore points, export and import.
step("POST", "/api/restore-points", {"label": "Before trying"})
step("POST", "/api/restore-points", {"label": "Before trying", "operation_id": "rp-1"})
POINT = len(STEPS) - 1
step("POST", "/api/restore-points", {"label": "Before trying", "operation_id": "rp-1"})
step("GET", "/api/restore-points")
step("GET", lambda replies: f"/api/restore-points/{replies[POINT].body['id']}/preview")  # type: ignore[index]
PREVIEW = len(STEPS) - 1
step("GET", "/api/restore-points/missing/preview")
step("POST", lambda replies: f"/api/restore-points/{replies[POINT].body['id']}/restore", {})  # type: ignore[index]
step(
    "POST",
    lambda replies: f"/api/restore-points/{replies[POINT].body['id']}/restore",  # type: ignore[index]
    lambda replies: {"state_token": replies[PREVIEW].body["state_token"], "operation_id": "re-1"},  # type: ignore[index]
)
step("POST", "/api/account-export", {"password": "wrong-password-1"})
step("POST", "/api/account-export", {"password": PASSWORD})
EXPORT = len(STEPS) - 1
step("POST", "/api/account-import/preview", lambda replies: {"snapshot": replies[EXPORT].body})
IMPORT_PREVIEW = len(STEPS) - 1
step("POST", "/api/account-import/preview", {"snapshot": {"format": "nope"}})
step("POST", "/api/account-import", lambda replies: {"snapshot": replies[EXPORT].body})
step(
    "POST",
    "/api/account-import",
    lambda replies: {
        "snapshot": replies[EXPORT].body,
        "state_token": replies[IMPORT_PREVIEW].body["state_token"],  # type: ignore[index]
        "operation_id": "imp-1",
    },
)
# The account itself, after the sign-in limit has forgotten the wrong passwords above.
step("CLOCK", "6")
step("POST", "/api/auth/recovery-codes", {"password": "wrong-password-1"})
step("POST", "/api/auth/recovery-codes", {"password": PASSWORD})
CODES = len(STEPS) - 1
step("GET", "/api/auth/recovery-status")
step("POST", "/api/auth/password", {"current_password": PASSWORD, "new_password": PASSWORD})
step("POST", "/api/auth/password", {"current_password": "wrong-password-1", "new_password": REPLACEMENT})
step("POST", "/api/auth/password", {"current_password": PASSWORD, "new_password": REPLACEMENT})
step("GET", "/api/auth/me")
step("POST", "/api/auth/logout")
step("GET", "/api/auth/me")
step("POST", "/api/auth/logout")
step("POST", "/api/auth/recover", {"username": "ana_1", "code": "WRONG-CODE-1234", "password": PASSWORD})
step(
    "POST",
    "/api/auth/recover",
    lambda replies: {
        "username": "ANA_1",
        "code": replies[CODES].body["recovery_codes"][0],  # type: ignore[index]
        "password": PASSWORD,
        "keep": False,
    },
)
step("GET", "/api/auth/recovery-status")
step("CLOCK", "6")
step("POST", "/api/auth/login", {"username": "ana_1", "password": PASSWORD})
step("DELETE", "/api/auth/account", {"password": "wrong-password-1"})
step("DELETE", "/api/auth/account", {"password": PASSWORD})
step("GET", "/api/auth/me")
step("CLOCK", "6")
step("POST", "/api/auth/login", {"username": "ana_1", "password": PASSWORD})
# Too many tries: the sign-in limit, then its answer.
for _ in range(12):
    step("POST", "/api/auth/login", {"username": "ana_2", "password": "wrong-password-1"})
step("POST", "/api/auth/register", {"username": "ana_3", "password": PASSWORD, "pad": "x" * 300_000})


def run(side: Server | Rust) -> Iterator[Reply]:
    replies: list[Reply] = []
    account: int | None = None
    for method, path, body in STEPS:
        if method == "CLOCK":
            CLOCK.move(minutes=float(path))  # type: ignore[arg-type]
            replies.append(Reply(0, None, "kept"))
            yield replies[-1]
            continue
        path = path(replies) if callable(path) else path  # type: ignore[operator]
        given = body(replies) if callable(body) else body
        text = given if isinstance(given, str) else ("" if given is None else json.dumps(given))
        reply = side.send(method, path, text, account)
        if reply.status in (200, 201) and isinstance(reply.body, dict) and "username" in reply.body:
            account = reply.body.get("id", account)  # type: ignore[assignment]
        if reply.session == "ended":
            account = None
        replies.append(reply)
        yield reply


def compared(reply: Reply) -> Reply:
    """What must match: a plan's own timing differs run to run, and the storage answer no longer names a
    server address, as there is none (the hosted server is gone, decision D4)."""
    body = reply.body
    if isinstance(body, dict):
        body = {key: value for key, value in body.items() if key not in {"solve_ms", "origin"}}
    return Reply(reply.status, body, reply.session)


def test_every_scripted_request_is_answered_as_the_server_answers_it(
    tmp_path: Path, same_randomness: Callable[[], None]
) -> None:
    server = Server(tmp_path / "server.db")
    try:
        heard = list(run(server))
    finally:
        server.close()
    same_randomness()
    CLOCK.reset()
    answered = list(run(Rust(tmp_path / "rust.db")))
    assert len(heard) == len(STEPS)
    statuses = {reply.status for reply in heard}
    # The script reaches every kind of answer the window tells apart.
    assert {200, 201, 204, 401, 404, 405, 409, 413, 422, 429} <= statuses, statuses
    differ = [
        (index, STEPS[index][:2], server_reply, rust_reply)
        for index, (server_reply, rust_reply) in enumerate(zip(heard, answered, strict=True))
        if compared(server_reply) != compared(rust_reply)
    ]
    assert not differ, "\n".join(map(repr, differ[:5]))
    assert heard[SIGNED_UP].status == 201
