import json
import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

import flexweek_engine  # type: ignore[import-untyped]
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from flexweek_engine import ServiceRefusal  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend import clock as wall_clock
from backend.availability import fold_study_windows
from backend.limits import MAX_BODY
from backend.models import (
    AssignmentContent,
    ProtectedWindow,
    StudyWindow,
    TimeBlock,
    WorkWindow,
    valid_spotify_url,
)
from backend.slots import DAY_END_MIN, SLOT_MIN
from backend.storage import (
    Connection,
    cookie_age,
    initialize,
)
from backend.weeks import (
    current_week_start,
)

ROOT = Path(__file__).resolve().parent.parent
COOKIE = "flexweek_session"
WEEK_START_RULE = "week_start must be a Monday from 2000-01-03 through 2099-12-28, or 1999-12-27"
DATE_RULE = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31"
MONTH_RULE = "month must be YYYY-MM between 2000-01 and 2099-12"
ASSIGNMENT_UNKNOWN = "assignment_id must name an assignment of this account"
ASSIGNMENT_LIMIT = "An account holds at most 1000 assignments"
MAX_ASSIGNMENTS = 1000
# The answer for each kind of refusal the Rust service gives (flexweek_service::Refusal).
REFUSAL_STATUS = {
    "invalid": 422,
    "unauthorized": 401,
    "not_found": 404,
    "conflict": 409,
    "too_many": 429,
    "too_large": 413,
}


def encode_assignment(content: AssignmentContent) -> str:
    return json.dumps(content.model_dump(), sort_keys=True, separators=(",", ":"))


def load_assignment_rows(db: Connection, user_id: int, ids: set[str]) -> dict[str, tuple[str, int]]:
    rows = db.load_assignment_rows(user_id, list(ids))
    return {row[0]: (row[1], int(row[2])) for row in rows}


def require_own_assignments(db: Connection, user_id: int, ids: set[str]) -> dict[str, dict]:
    owned, rows = db.require_own_assignments(user_id, list(ids))
    found = {row[0]: json.loads(row[1]) for row in rows}
    if not owned:
        raise HTTPException(422, ASSIGNMENT_UNKNOWN)
    return found


def encode_new_assignment(text: str) -> str:
    return encode_assignment(AssignmentContent.model_validate(json.loads(text)))


def adopt_legacy_deadlines(
    db: Connection, user_id: int, week_start: str, blocks: list[TimeBlock]
) -> list[TimeBlock]:
    fits, adopted = db.adopt_legacy_deadlines(
        user_id,
        week_start,
        json.dumps([block.model_dump() for block in blocks]),
        MAX_ASSIGNMENTS,
        encode_new_assignment,
    )
    if not fits:
        raise HTTPException(422, ASSIGNMENT_LIMIT)
    return [TimeBlock.model_validate(item) for item in json.loads(adopted)]


def rewrite_blocks(blocks: list[TimeBlock], assignments: dict[str, dict]) -> list[TimeBlock]:
    rewritten = flexweek_engine.rewrite_blocks(
        json.dumps([block.model_dump() for block in blocks]), json.dumps(assignments)
    )
    return [TimeBlock.model_validate(item) for item in json.loads(rewritten)]


def normalize_stored_block(text: str) -> str:
    return json.dumps(TimeBlock.model_validate(json.loads(text)).model_dump())


def rewrite_stored_blocks(blocks: list[dict], assignments: dict[str, dict]) -> list[dict]:
    rewritten = flexweek_engine.rewrite_stored_blocks(
        json.dumps(blocks), json.dumps(assignments), normalize_stored_block
    )
    loaded: list[dict] = json.loads(rewritten)
    return loaded


def list_account_weeks(db: Connection, user_id: int) -> list[tuple[str, list[dict]]]:
    rows = db.list_account_weeks(user_id)
    return [(row[0], json.loads(row[1])) for row in rows]


def week_with_standing(db: Connection, user_id: int, week_start: str, stored: str | None) -> list[dict]:
    """A week as the student sees it: its own blocks and the School and activities standing in it."""
    merged: list[dict] = json.loads(db.week_with_standing(user_id, week_start, stored or "[]"))
    return merged


def assignment_view(body: dict, revision: int, planned: int, done: int = 0) -> dict:
    view: dict = json.loads(flexweek_engine.assignment_view(json.dumps(body), revision, planned, done))
    return view


def naive_now() -> str:
    return wall_clock.now().strftime("%Y-%m-%dT%H:%M")


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=12, max_length=128)
    keep: bool = False

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


# School, Setup's activities and weekly fixed times together; the engine holds the number (#118).
# One save can stop every repeat and add as many new ones.


class AlarmPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    time: str = Field(pattern=r"(?:[01]\d|2[0-3]):[0-5]\d")
    days: list[int] = Field(min_length=1, max_length=7)
    enabled: bool = True
    sound: Literal["chime", "soft", "bright", "low", "glass", "spotify"] = "chime"
    spotify_url: str | None = Field(default=None, max_length=500)

    @field_validator("days")
    @classmethod
    def valid_days(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("alarm days must be unique values in 0..6")
        return sorted(value)

    _spotify_url = field_validator("spotify_url")(valid_spotify_url)


class SetupProgress(BaseModel):
    """Where first-run setup stands, so a skip or a finish is remembered and a quit resumes."""

    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, le=100)
    step: int = Field(default=0, ge=0, le=20)
    finished_at: str | None = Field(default=None, max_length=32)

    @field_validator("finished_at")
    @classmethod
    def finished_at_is_a_timestamp(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?", value):
            raise ValueError("finished_at must be YYYY-MM-DDTHH:MM")
        return value


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "system" follows the device light/dark setting; slate is Light and nocturne is Dark.
    theme: Literal["system", "slate", "nocturne"]
    reminders_enabled: bool = True
    reminder_lead_min: int = Field(default=5, ge=0, le=120)
    reminder_sound: bool = True
    reminder_dnd_override: bool = False
    timer_work_min: int = Field(default=30, ge=1, le=180)
    timer_break_min: int = Field(default=15, ge=1, le=60)
    timer_long_break_min: int = Field(default=30, ge=1, le=120)
    timer_long_break_every: int = Field(default=4, ge=2, le=12)
    auto_split_pomodoro: bool = False
    default_spotify_url: str | None = Field(default=None, max_length=500)
    alarms: list[AlarmPreference] = Field(default_factory=list, max_length=20)
    protected: list[ProtectedWindow] = Field(
        default_factory=list, max_length=21, exclude_if=lambda value: not value
    )
    # Study hours: the one list the planner may use (J7). Older builds also sent preferred
    # study hours as `study_windows`; carry_preferred_study_hours folds them in.
    work_windows: list[WorkWindow] = Field(
        default_factory=list, max_length=21, exclude_if=lambda value: not value
    )
    day_cutoff: str | None = Field(default=None, exclude_if=lambda value: value is None)
    # Planner switches. Omitted at the default so an account that never set them
    # reads as weekends open, a 15-minute gap, urgent first, no split. An explicit
    # 0 for the buffer is stored so None is not the same as never set.
    weekend_homework_free: bool = Field(default=False, exclude_if=lambda value: value is False)
    buffer_min: Literal[0, 15, 30] = Field(default=15, exclude_if=lambda value: value == 15)
    urgent_first: bool = Field(default=True, exclude_if=lambda value: value is True)
    split_long_tasks: bool = Field(default=False, exclude_if=lambda value: value is False)
    # The week grid reads this. The planner does not.
    show_weekends: bool = Field(default=True, exclude_if=lambda value: value is True)
    alert_volume: int = Field(default=80, ge=0, le=100, exclude_if=lambda value: value == 80)
    end_chime: bool = Field(default=False, exclude_if=lambda value: value is False)
    tray_notifications: bool = Field(default=True, exclude_if=lambda value: value is True)
    start_at_login: bool = Field(default=False, exclude_if=lambda value: value is False)
    preferred_view: Literal["week", "day", "month", "myday"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    sidebar_collapsed: bool = Field(default=False, exclude_if=lambda value: value is False)
    sidebar_width_px: int | None = Field(default=None, ge=200, le=640, exclude_if=lambda value: value is None)
    theme_pack: Literal["system", "light-frost", "dark-frost", "nocturne", "slate"] = Field(
        default="system", exclude_if=lambda value: value == "system"
    )
    accent: Literal["default", "sky", "gold", "sea", "sand"] = Field(
        default="default", exclude_if=lambda value: value == "default"
    )
    accent_chips: bool = Field(default=False, exclude_if=lambda value: value is False)
    motion: Literal["off", "normal", "extra", "reduce"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # One sound for reminders, the end of a focus session and new alarms. "spotify" plays
    # default_spotify_url instead.
    alarm_tone: Literal["chime", "soft", "bright", "low", "glass", "spotify"] = Field(
        default="chime", exclude_if=lambda value: value == "chime"
    )
    # How homework gets a time: as it is added, when Plan my homework is pressed, or by dragging.
    planning_style: Literal["auto", "suggest", "manual"] = Field(
        default="suggest", exclude_if=lambda value: value == "suggest"
    )
    # Minutes a dragged, resized or drawn block moves by. Typed times are any minute either way.
    # 15 unless chosen otherwise, so a chosen 5 is the one that is sent.
    drag_step_min: Literal[5, 15] = Field(default=15, exclude_if=lambda value: value == 15)
    # Times on screen as 16:00 or as 4:00 PM. Stored and sent as HH:MM either way. 12-hour for a
    # new account; an account from before 0.18.5 that never chose is stamped 24-hour when the store
    # opens.
    clock_24h: bool = Field(default=False, exclude_if=lambda value: value is False)
    # What plays when focus starts. Off is omitted, as the other comfort defaults are. Kept in
    # comfort_json, on this computer: a synced column would make an older phone update a column it
    # does not have.
    focus_audio: Literal["off", "rain", "lo-fi", "white-noise", "spotify"] = Field(
        default="off", exclude_if=lambda value: value == "off"
    )
    # Material 3's focus rules. Auto-mute holds reminders until the focus work phase is over;
    # auto-complete moves the finished session's block to Done. Both are comfort values like the
    # audio choice, each omitted at its default.
    focus_auto_mute: bool = Field(default=True, exclude_if=lambda value: value is True)
    focus_auto_complete: bool = Field(default=False, exclude_if=lambda value: value is False)
    setup: SetupProgress | None = Field(default=None, exclude_if=lambda value: value is None)

    _spotify_url = field_validator("default_spotify_url")(valid_spotify_url)

    @model_validator(mode="before")
    @classmethod
    def carry_preferred_study_hours(cls, data: object) -> object:
        """An export file or client from before the one list may still send preferred study hours.
        They join Study hours here, as they do where saved preferences are read."""
        if not isinstance(data, dict) or "study_windows" not in data:
            return data
        data = dict(data)
        study = [StudyWindow.model_validate(item) for item in data.pop("study_windows") or []]
        if study:
            work = [WorkWindow.model_validate(item) for item in data.get("work_windows") or []]
            data["work_windows"] = fold_study_windows(work, study)
        return data

    @field_validator("day_cutoff")
    @classmethod
    def cutoff_is_on_the_grid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("day_cutoff must be HH:MM on the 15-minute grid")
        hour, minute = map(int, value.split(":"))
        start = hour * 60 + minute
        if minute % 15 or start < SLOT_MIN or start > DAY_END_MIN - SLOT_MIN:
            raise ValueError("day_cutoff must be between 00:15 and 23:45 on the 15-minute grid")
        return value

    @model_validator(mode="after")
    def protected_windows_do_not_overlap(self) -> Preferences:
        # Half-open [start, end) ranges, checked per day: touching windows and
        # windows on disjoint days are fine.
        for day in range(7):
            intervals: list[tuple[int, int]] = []
            for window in self.protected:
                if day not in window.days:
                    continue
                hour, minute = map(int, window.start.split(":"))
                start = hour * 60 + minute
                end = start + window.duration_min
                if any(start < other_end and other_start < end for other_start, other_end in intervals):
                    raise ValueError("protected windows must not overlap on a shared day")
                intervals.append((start, end))
        return self

    @model_validator(mode="after")
    def split_lengths_are_on_the_grid(self) -> Preferences:
        if not self.auto_split_pomodoro:
            return self
        for length in (self.timer_work_min, self.timer_break_min, self.timer_long_break_min):
            if length % 15:
                raise ValueError("auto_split_pomodoro needs 15-minute work and break lengths")
        return self

    @model_validator(mode="after")
    def pack_keeps_theme_on_its_axis(self) -> Preferences:
        if self.theme_pack == "system":
            return self
        axis = "slate" if self.theme_pack in {"light-frost", "slate"} else "nocturne"
        if self.theme != axis:
            raise ValueError("theme_pack needs theme on the same light or dark axis")
        return self


class PasswordConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class RecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    code: str = Field(min_length=8, max_length=64)
    password: str = Field(min_length=12, max_length=128)
    keep: bool = False

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


def create_app(database: Path | None = None, origin: str | None = None) -> FastAPI:
    path = database or Path(os.environ.get("FLEXWEEK_DATABASE", str(ROOT / "var" / "flexweek.db")))
    public_origin = (origin or os.environ.get("FLEXWEEK_ORIGIN", "http://127.0.0.1:8000")).rstrip("/")
    parsed = urlsplit(public_origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path or parsed.query:
        raise ValueError("FLEXWEEK_ORIGIN must be an http(s) origin without a path")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "testserver"}:
        raise ValueError("Non-local deployments require an HTTPS origin")
    secure = parsed.scheme == "https"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(path)
        yield

    app = FastAPI(title="FlexWeek", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[parsed.hostname])

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if (
                request.headers.get("X-FlexWeek-Request") != "1"
                or request.headers.get("origin", public_origin) != public_origin
                or request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return JSONResponse({"detail": "Request origin rejected"}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic errors otherwise echo rejected passwords into the response.
        return JSONResponse(
            {"detail": "Invalid input. Check field lengths, times and required values."}, status_code=422
        )

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, exc: sqlite3.OperationalError):
        return JSONResponse(
            {"detail": "Storage unavailable. Your changes were not saved; retry shortly."}, status_code=503
        )

    store_path = str(path)

    def refused(error: ServiceRefusal) -> HTTPException:
        kind, words = error.args
        headers = {"Retry-After": "300"} if kind == "too_many" else None
        return HTTPException(REFUSAL_STATUS[kind], words, headers=headers)

    def asked(request: Request) -> tuple[str, int]:
        return (request.client.host if request.client else "unknown"), int(wall_clock.seconds())

    def user(request: Request) -> dict:
        try:
            found = flexweek_engine.service_signed_in(
                store_path,
                request.cookies.get(COOKIE, ""),
                int(wall_clock.seconds()),
                request.headers.get("X-FlexWeek-Account"),
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        return {"id": found[0], "username": found[1]}

    def session_response(response: Response, token: str, keep: bool = False) -> None:
        response.set_cookie(
            COOKIE,
            token,
            max_age=cookie_age(keep),
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/",
        )

    def authenticate(data: Credentials, request: Request, response: Response, register: bool) -> dict:
        address, now = asked(request)
        signing = flexweek_engine.service_register if register else flexweek_engine.service_login
        try:
            previous = request.cookies.get(COOKIE, "")
            user_id, username, token, codes = signing(
                store_path, address, now, data.username, data.password, data.keep, previous
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        session_response(response, token, data.keep)
        result: dict = {"id": user_id, "username": username}
        if codes is not None:
            result["recovery_codes"] = codes
        return result

    @app.post("/api/auth/register", status_code=201)
    def register(data: Credentials, request: Request, response: Response) -> dict:
        return authenticate(data, request, response, True)

    @app.post("/api/auth/login")
    def login(data: Credentials, request: Request, response: Response) -> dict:
        return authenticate(data, request, response, False)

    @app.get("/api/auth/me")
    def me(account: Annotated[dict, Depends(user)]) -> dict:
        return account

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response) -> None:
        try:
            flexweek_engine.service_logout(
                store_path,
                request.cookies.get(COOKIE, ""),
                int(wall_clock.seconds()),
                request.headers.get("X-FlexWeek-Account"),
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        response.delete_cookie(COOKIE, path="/", httponly=True, secure=secure, samesite="strict")

    @app.post("/api/auth/recover")
    def recover(data: RecoverRequest, request: Request, response: Response) -> dict:
        address, now = asked(request)
        try:
            user_id, username, token, _ = flexweek_engine.service_recover(
                store_path, address, now, data.username, data.code, data.password, data.keep
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        session_response(response, token, data.keep)
        return {"id": user_id, "username": username}

    @app.get("/api/auth/recovery-status")
    def recovery_status(account: Annotated[dict, Depends(user)]) -> dict:
        return {"remaining": flexweek_engine.service_recovery_codes_left(store_path, account["id"])}

    @app.post("/api/auth/recovery-codes")
    def refresh_recovery_codes(
        data: PasswordConfirm, request: Request, account: Annotated[dict, Depends(user)]
    ) -> dict:
        address, now = asked(request)
        try:
            codes = flexweek_engine.service_renew_recovery_codes(
                store_path, address, now, account["id"], account["username"], data.password
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        return {"recovery_codes": codes, "remaining": len(codes)}

    @app.post("/api/auth/password")
    def change_password(
        data: PasswordChange, request: Request, response: Response, account: Annotated[dict, Depends(user)]
    ) -> dict:
        address, now = asked(request)
        try:
            token = flexweek_engine.service_change_password(
                store_path,
                address,
                now,
                account["id"],
                account["username"],
                data.current_password,
                data.new_password,
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        session_response(response, token)
        return {"id": account["id"], "username": account["username"]}

    @app.delete("/api/auth/account", status_code=204)
    def remove_account(
        data: PasswordConfirm, request: Request, response: Response, account: Annotated[dict, Depends(user)]
    ) -> None:
        address, now = asked(request)
        try:
            flexweek_engine.service_delete_account(
                store_path, address, now, account["id"], account["username"], data.password
            )
        except ServiceRefusal as error:
            raise refused(error) from None
        response.delete_cookie(COOKIE, path="/", httponly=True, secure=secure, samesite="strict")

    async def sent_json(request: Request) -> str:
        """The body as the client sent it, for the service to read: re-writing the parsed copy would turn a
        number too large for a float into `Infinity`, which is not JSON. The routes keep their parsed `given`
        so FastAPI still answers a body that is not a JSON object as before."""
        body = await request.body()
        try:
            # Decoded as json.loads decodes bytes (UTF-8, -16 or -32), so the service reads what FastAPI read.
            text = body.decode(json.detect_encoding(body), "surrogatepass")
            text.encode("utf-8")
        except UnicodeError:
            return ""
        return text

    def served(call, *args) -> dict:  # type: ignore[no-untyped-def]
        """One read from the Rust service; a refusal is its answer with Python's sentence."""
        try:
            answer: dict = json.loads(call(store_path, *args))
        except ServiceRefusal as error:
            raise refused(error) from None
        return answer

    @app.get("/api/week")
    def get_week(account: Annotated[dict, Depends(user)], week_start: str | None = None) -> dict:
        start = week_start if week_start is not None else current_week_start()
        return served(flexweek_engine.service_read_week, account["id"], start)

    @app.get("/api/weeks")
    def get_weeks(account: Annotated[dict, Depends(user)]) -> dict:
        return served(flexweek_engine.service_list_weeks, account["id"])

    @app.get("/api/day")
    def get_day(account: Annotated[dict, Depends(user)], date: str | None = None) -> dict:
        if date is None:
            raise HTTPException(422, DATE_RULE)
        return served(flexweek_engine.service_day, account["id"], date, naive_now())

    @app.get("/api/month")
    def get_month(
        account: Annotated[dict, Depends(user)],
        month: str | None = None,
        first_day: Annotated[int, Query(ge=0, le=6)] = 0,
    ) -> dict:
        """`first_day` is the day the rows start on (0 Monday to 6 Sunday), as the computer shows it."""
        if month is None:
            raise HTTPException(422, MONTH_RULE)
        return served(flexweek_engine.service_month, account["id"], month, first_day, naive_now())

    @app.put("/api/week")
    def put_week(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        return served(flexweek_engine.service_save_week, account["id"], sent)

    @app.get("/api/assignments")
    def get_assignments(
        account: Annotated[dict, Depends(user)],
        week_start: str | None = None,
        include_completed: bool = False,
    ) -> dict:
        if week_start is None:
            raise HTTPException(422, WEEK_START_RULE)
        listed = flexweek_engine.service_homework
        return served(listed, account["id"], week_start, include_completed, naive_now())

    @app.put("/api/assignments/{assignment_id}")
    def put_assignment(
        assignment_id: str,
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        saved = flexweek_engine.service_save_homework
        return served(saved, account["id"], assignment_id, sent)

    @app.post("/api/assignments/{assignment_id}/spread")
    def post_spread(
        assignment_id: str,
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        preview = flexweek_engine.service_spread_preview
        return served(preview, account["id"], assignment_id, sent)

    @app.delete("/api/assignments/{assignment_id}")
    def remove_assignment(
        assignment_id: str, account: Annotated[dict, Depends(user)], revision: int | None = None
    ) -> dict:
        if revision is None:
            raise HTTPException(422, "revision is required")
        return served(flexweek_engine.service_delete_homework, account["id"], assignment_id, revision)

    @app.post("/api/repeat-edits")
    def post_repeat_edits(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        return served(flexweek_engine.service_repeat_edits, account["id"], sent)

    @app.post("/api/changes")
    def post_changes(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        changed = flexweek_engine.service_changes
        return served(changed, account["id"], sent, secrets.token_hex(8), naive_now())

    @app.get("/api/preferences")
    def get_preferences(account: Annotated[dict, Depends(user)]) -> dict:
        return served(flexweek_engine.service_read_preferences, account["id"])

    @app.put("/api/preferences")
    def put_preferences(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        return served(flexweek_engine.service_write_preferences, account["id"], sent)

    @app.get("/api/routines")
    def get_routines(account: Annotated[dict, Depends(user)]) -> dict:
        return served(flexweek_engine.service_routines, account["id"])

    @app.put("/api/routines/{routine_id}")
    def put_routine(
        routine_id: str,
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        saved = flexweek_engine.service_save_routine
        return served(saved, account["id"], routine_id, sent, naive_now())

    @app.delete("/api/routines/{routine_id}")
    def remove_routine(
        routine_id: str,
        account: Annotated[dict, Depends(user)],
        revision: int | None = None,
        operation_id: str | None = None,
    ) -> dict:
        if revision is None:
            raise HTTPException(422, "revision is required")
        deleting = flexweek_engine.service_delete_routine
        return served(deleting, account["id"], routine_id, revision, operation_id)

    @app.get("/api/storage-info")
    def get_storage_info(account: Annotated[dict, Depends(user)]) -> dict:
        hostname = parsed.hostname or ""
        if hostname in {"127.0.0.1", "localhost", "testserver"}:
            mode, label = "local", "On this device"
        else:
            mode, label = "hosted", "On your FlexWeek server"
        return {
            "mode": mode,
            "label": label,
            "username": account["username"],
            "origin": public_origin,
            "transfer_limit_bytes": MAX_BODY,
        }

    @app.post("/api/account-export")
    def export_account(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        request: Request,
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        address, now = asked(request)
        exported = flexweek_engine.service_export_account
        return served(exported, address, now, account["id"], account["username"], sent, naive_now())

    @app.post("/api/account-import/preview")
    def preview_account_import(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        return served(flexweek_engine.service_import_preview, account["id"], sent)

    @app.post("/api/account-import")
    def apply_account_import(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        imported = flexweek_engine.service_import_account
        return served(imported, account["id"], sent, secrets.token_hex(8), naive_now())

    @app.get("/api/timer-presets")
    def get_timer_presets(_account: Annotated[dict, Depends(user)]) -> dict:
        return {"presets": json.loads(flexweek_engine.timer_presets())}

    @app.get("/api/reminder-limits")
    def get_reminder_limits(_account: Annotated[dict, Depends(user)]) -> dict:
        answer: dict = json.loads(flexweek_engine.reminder_limits())
        return answer

    @app.post("/api/timer-split-preview")
    def post_timer_split_preview(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        _account: Annotated[dict, Depends(user)],
    ) -> dict:
        try:
            answer: dict = json.loads(flexweek_engine.service_split_preview(sent))
        except ServiceRefusal as error:
            raise refused(error) from None
        return answer

    @app.get("/api/restore-points")
    def get_restore_points(account: Annotated[dict, Depends(user)]) -> dict:
        return served(flexweek_engine.service_restore_points, account["id"])

    @app.post("/api/restore-points")
    def post_restore_point(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        made = flexweek_engine.service_create_restore_point
        return served(made, account["id"], sent, secrets.token_hex(8), naive_now())

    @app.get("/api/restore-points/{point_id}/preview")
    def preview_restore_point(point_id: str, account: Annotated[dict, Depends(user)]) -> dict:
        return served(flexweek_engine.service_restore_preview, account["id"], point_id)

    @app.post("/api/restore-points/{point_id}/restore")
    def restore_restore_point(
        point_id: str,
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        restored = flexweek_engine.service_restore
        return served(
            restored, account["id"], point_id, sent, secrets.token_hex(8), naive_now()
        )

    @app.post("/api/solve")
    def post_solve(
        given: Annotated[dict, Body()],
        sent: Annotated[str, Depends(sent_json)],
        account: Annotated[dict, Depends(user)],
    ) -> dict:
        return served(flexweek_engine.service_plan, account["id"], sent)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()
