import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.assignments import (
    legacy_session,
    planned_minutes_by_id,
    prepare_solve,
    rewrite_session,
    unplanned_minutes,
)
from backend.day import build_day
from backend.models import (
    Assignment,
    AssignmentContent,
    SolveRequest,
    TimeBlock,
    WeekRequest,
    valid_spotify_url,
)
from backend.solver import reschedule_after_miss, solve
from backend.storage import (
    SESSION_SECONDS,
    connect,
    create_session,
    digest,
    initialize,
    password_hash,
    password_matches,
    throttle,
)
from backend.weeks import current_week_start, is_calendar_date, is_week_start, monday_of

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
COOKIE = "flexweek_session"
MAX_BODY = 256 * 1024
WEEK_START_RULE = "week_start must be a Monday date between 2000-01-01 and 2099-12-31"
DATE_RULE = "date must be YYYY-MM-DD between 2000-01-01 and 2099-12-31"
ASSIGNMENT_UNKNOWN = "assignment_id must name an assignment of this account"
ASSIGNMENT_CONFLICT = "This assignment changed in another window. Reload before saving."
ASSIGNMENT_LIMIT = "An account holds at most 1000 assignments"
WEEK_CONFLICT = "This week changed in another window. Reload before saving."
MAX_ASSIGNMENTS = 1000


def encode_assignment(content: AssignmentContent) -> str:
    return json.dumps(content.model_dump(), sort_keys=True, separators=(",", ":"))


def assignment_ids_of(blocks: list[TimeBlock]) -> set[str]:
    return {block.assignment_id for block in blocks if block.assignment_id}


def load_assignment_rows(
    db: sqlite3.Connection, user_id: int, ids: set[str]
) -> dict[str, tuple[str, int]]:
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = db.execute(
        f"SELECT id, body, revision FROM assignments WHERE user_id = ? AND id IN ({placeholders})",
        (user_id, *ids),
    ).fetchall()
    return {row["id"]: (row["body"], row["revision"]) for row in rows}


def load_assignment_bodies(db: sqlite3.Connection, user_id: int, ids: set[str]) -> dict[str, dict]:
    loaded = load_assignment_rows(db, user_id, ids)
    return {key: json.loads(body) for key, (body, _revision) in loaded.items()}


def require_own_assignments(db: sqlite3.Connection, user_id: int, ids: set[str]) -> dict[str, dict]:
    found = load_assignment_bodies(db, user_id, ids)
    if found.keys() != ids:
        raise HTTPException(422, ASSIGNMENT_UNKNOWN)
    return found


def adopt_legacy_deadlines(
    db: sqlite3.Connection, user_id: int, week_start: str, blocks: list[TimeBlock]
) -> list[TimeBlock]:
    adopted: list[TimeBlock] = []
    created: list[dict] = []
    for block in blocks:
        if block.kind != "flexible" or block.assignment_id or not block.latest:
            adopted.append(block)
            continue
        session, body = legacy_session(week_start, block)
        exists = db.execute(
            "SELECT 1 FROM assignments WHERE user_id = ? AND id = ?", (user_id, body["id"])
        ).fetchone()
        if exists is None:
            created.append(body)
        adopted.append(session)
    if created:
        count = db.execute("SELECT COUNT(*) AS n FROM assignments WHERE user_id = ?", (user_id,)).fetchone()
        if int(count["n"]) + len(created) > MAX_ASSIGNMENTS:
            raise HTTPException(422, ASSIGNMENT_LIMIT)
        for body in created:
            db.execute(
                "INSERT INTO assignments(user_id, id, body, revision) VALUES (?, ?, ?, 1)",
                (user_id, body["id"], encode_assignment(AssignmentContent.model_validate(body))),
            )
    return adopted


def rewrite_blocks(blocks: list[TimeBlock], assignments: dict[str, dict]) -> list[TimeBlock]:
    rewritten: list[TimeBlock] = []
    for block in blocks:
        if block.assignment_id:
            rewritten.append(rewrite_session(block, assignments[block.assignment_id]))
        else:
            rewritten.append(block)
    return rewritten


def rewrite_stored_blocks(blocks: list[dict], assignments: dict[str, dict]) -> list[dict]:
    rewritten: list[dict] = []
    for raw in blocks:
        aid = raw.get("assignment_id")
        if not aid or aid not in assignments:
            rewritten.append(raw)
            continue
        rewritten.append(rewrite_session(TimeBlock.model_validate(raw), assignments[aid]).model_dump())
    return rewritten


def dump_blocks(blocks: list[TimeBlock]) -> list[dict]:
    return [block.model_dump() for block in blocks]


def list_account_weeks(db: sqlite3.Connection, user_id: int) -> list[tuple[str, list[dict]]]:
    rows = db.execute("SELECT week_start, blocks FROM weeks WHERE user_id = ?", (user_id,)).fetchall()
    return [(row["week_start"], json.loads(row["blocks"])) for row in rows]


def assignment_view(body: dict, revision: int, planned: int) -> dict:
    return {
        **body,
        "revision": revision,
        "planned_min": planned,
        "unplanned_min": unplanned_minutes(int(body["estimate_min"]), int(body["focus_minutes"]), planned),
    }


def upsert_assignment(
    db: sqlite3.Connection, user_id: int, content: AssignmentContent, revision: int
) -> dict:
    encoded = encode_assignment(content)
    row = db.execute(
        "SELECT body, revision FROM assignments WHERE user_id = ? AND id = ?", (user_id, content.id)
    ).fetchone()
    stored, stored_revision = (row["body"], row["revision"]) if row else (None, 0)
    if stored == encoded:
        return {**content.model_dump(), "revision": stored_revision}
    if revision != stored_revision:
        raise HTTPException(409, ASSIGNMENT_CONFLICT)
    if stored is None:
        count = db.execute("SELECT COUNT(*) AS n FROM assignments WHERE user_id = ?", (user_id,)).fetchone()
        if int(count["n"]) >= MAX_ASSIGNMENTS:
            raise HTTPException(422, ASSIGNMENT_LIMIT)
        db.execute(
            "INSERT INTO assignments(user_id, id, body, revision) VALUES (?, ?, ?, 1)",
            (user_id, content.id, encoded),
        )
        return {**content.model_dump(), "revision": 1}
    db.execute(
        "UPDATE assignments SET body = ?, revision = revision + 1 WHERE user_id = ? AND id = ?",
        (encoded, user_id, content.id),
    )
    return {**content.model_dump(), "revision": revision + 1}


def delete_assignment(db: sqlite3.Connection, user_id: int, assignment_id: str, revision: int) -> dict:
    row = db.execute(
        "SELECT revision FROM assignments WHERE user_id = ? AND id = ?", (user_id, assignment_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Assignment not found")
    if revision != row["revision"]:
        raise HTTPException(409, ASSIGNMENT_CONFLICT)
    weeks = db.execute(
        "SELECT week_start, blocks, revision FROM weeks WHERE user_id = ? ORDER BY week_start",
        (user_id,),
    ).fetchall()
    changed_weeks: list[dict] = []
    removed_sessions: dict[str, list[dict]] = {}
    for week in weeks:
        blocks = json.loads(week["blocks"])
        kept = [block for block in blocks if block.get("assignment_id") != assignment_id]
        removed = [block for block in blocks if block.get("assignment_id") == assignment_id]
        if not removed:
            continue
        new_revision = week["revision"] + 1
        db.execute(
            "UPDATE weeks SET blocks = ?, revision = ? WHERE user_id = ? AND week_start = ?",
            (
                json.dumps(kept, sort_keys=True, separators=(",", ":")),
                new_revision,
                user_id,
                week["week_start"],
            ),
        )
        changed_weeks.append({"week_start": week["week_start"], "revision": new_revision})
        removed_sessions[week["week_start"]] = removed
    db.execute("DELETE FROM assignments WHERE user_id = ? AND id = ?", (user_id, assignment_id))
    return {"changed_weeks": changed_weeks, "removed_sessions": removed_sessions}


def save_week_row(
    db: sqlite3.Connection,
    user_id: int,
    week_start: str,
    blocks: list[dict],
    revision: int,
) -> tuple[list[dict], int]:
    encoded = json.dumps(blocks, sort_keys=True, separators=(",", ":"))
    row = db.execute(
        "SELECT blocks, revision FROM weeks WHERE user_id = ? AND week_start = ?",
        (user_id, week_start),
    ).fetchone()
    stored, stored_revision = (row["blocks"], row["revision"]) if row else ("[]", 0)
    if encoded == stored:
        return blocks, stored_revision
    if revision != stored_revision:
        raise HTTPException(409, WEEK_CONFLICT)
    db.execute(
        """INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id, week_start)
        DO UPDATE SET blocks = excluded.blocks, revision = revision + 1""",
        (user_id, week_start, encoded),
    )
    return blocks, revision + 1


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


class SavedWeek(WeekRequest):
    model_config = ConfigDict(extra="forbid")
    week_start: str
    revision: int = Field(ge=0, le=2**53 - 1)

    @field_validator("week_start")
    @classmethod
    def week_start_is_a_monday(cls, value: str) -> str:
        if not is_week_start(value):
            raise ValueError(WEEK_START_RULE)
        return value


class AssignmentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    assignment: AssignmentContent | None
    revision: int = Field(ge=0, le=2**53 - 1)


class ChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weeks: list[SavedWeek] = Field(default_factory=list)
    assignments: list[AssignmentChange] = Field(default_factory=list)


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


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "system" follows the device light/dark setting; slate is Light and nocturne is Dark.
    theme: Literal["system", "slate", "nocturne"]
    reminders_enabled: bool = False
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

    _spotify_url = field_validator("default_spotify_url")(valid_spotify_url)


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

    def user(request: Request) -> dict:
        token = request.cookies.get(COOKIE, "")
        with connect(path) as db:
            row = db.execute(
                """SELECT users.id, users.username FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE token_hash = ? AND expires > ?""",
                (digest(token), int(time.time())),
            ).fetchone()
        if row is None:
            raise HTTPException(401, "Please sign in")
        expected = request.headers.get("X-FlexWeek-Account")
        if expected is not None and expected != str(row["id"]):
            raise HTTPException(401, "Account changed. Please sign in again.")
        return dict(row)

    def session_response(response: Response, token: str) -> None:
        response.set_cookie(
            COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=secure, samesite="strict", path="/"
        )

    def authenticate(data: Credentials, request: Request, response: Response, register: bool) -> dict:
        address = request.client.host if request.client else "unknown"
        if not throttle(path, address, data.username):
            raise HTTPException(
                429, "Too many attempts. Try again in five minutes.", headers={"Retry-After": "300"}
            )
        if register:
            encoded = password_hash(data.password)
            try:
                with connect(path) as db:
                    cursor = db.execute(
                        "INSERT INTO users(username, password_hash) VALUES (?, ?)", (data.username, encoded)
                    )
                    user_id = int(cursor.lastrowid or 0)
                    db.execute("INSERT INTO preferences(user_id) VALUES (?)", (user_id,))
                    token = create_session(db, user_id)
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "Username unavailable") from exc
        else:
            with connect(path) as db:
                row = db.execute("SELECT * FROM users WHERE username = ?", (data.username,)).fetchone()
            encoded = row["password_hash"] if row else password_hash("missing-account-password", "00" * 16)
            matched = password_matches(data.password, encoded)
            if not row or not matched:
                raise HTTPException(401, "Incorrect username or password")
            user_id = row["id"]
            with connect(path) as db:
                token = create_session(db, user_id)
        with connect(path) as db:
            db.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (digest(request.cookies.get(COOKIE, "")),)
            )
        session_response(response, token)
        return {"id": user_id, "username": data.username}

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
        if request.headers.get("X-FlexWeek-Account") is not None:
            user(request)
        with connect(path) as db:
            db.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (digest(request.cookies.get(COOKIE, "")),)
            )
        response.delete_cookie(COOKIE, path="/", httponly=True, secure=secure, samesite="strict")

    @app.get("/api/week")
    def get_week(account: Annotated[dict, Depends(user)], week_start: str | None = None) -> dict:
        start = week_start if week_start is not None else current_week_start()
        if not is_week_start(start):
            raise HTTPException(422, WEEK_START_RULE)
        with connect(path) as db:
            row = db.execute(
                "SELECT blocks, revision FROM weeks WHERE user_id = ? AND week_start = ?",
                (account["id"], start),
            ).fetchone()
            blocks = json.loads(row["blocks"]) if row else []
            owned = load_assignment_bodies(
                db,
                account["id"],
                {block["assignment_id"] for block in blocks if block.get("assignment_id")},
            )
        # A week nobody has saved yet is empty, not missing: the client needs no create-then-fetch.
        return {
            "week_start": start,
            "blocks": rewrite_stored_blocks(blocks, owned),
            "revision": row["revision"] if row else 0,
        }

    @app.get("/api/weeks")
    def get_weeks(account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            rows = db.execute(
                "SELECT week_start FROM weeks WHERE user_id = ? ORDER BY week_start", (account["id"],)
            ).fetchall()
        return {"weeks": [row["week_start"] for row in rows]}

    @app.get("/api/day")
    def get_day(account: Annotated[dict, Depends(user)], date: str | None = None) -> dict:
        if date is None or not is_calendar_date(date):
            raise HTTPException(422, DATE_RULE)
        week_start = monday_of(date)
        with connect(path) as db:
            row = db.execute(
                "SELECT blocks FROM weeks WHERE user_id = ? AND week_start = ?",
                (account["id"], week_start),
            ).fetchone()
            blocks = json.loads(row["blocks"]) if row else []
            owned = load_assignment_bodies(
                db,
                account["id"],
                {block["assignment_id"] for block in blocks if block.get("assignment_id")},
            )
            assignment_rows = [
                (json.loads(item["body"]), int(item["revision"]))
                for item in db.execute(
                    "SELECT body, revision FROM assignments WHERE user_id = ?", (account["id"],)
                ).fetchall()
            ]
            weeks = list_account_weeks(db, account["id"])
        return build_day(date, week_start, rewrite_stored_blocks(blocks, owned), assignment_rows, weeks)

    @app.put("/api/week")
    def put_week(week: SavedWeek, account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            incoming = adopt_legacy_deadlines(db, account["id"], week.week_start, week.blocks)
            owned = require_own_assignments(db, account["id"], assignment_ids_of(incoming))
            blocks = dump_blocks(rewrite_blocks(incoming, owned))
            stored_blocks, revision = save_week_row(
                db, account["id"], week.week_start, blocks, week.revision
            )
        return {"week_start": week.week_start, "blocks": stored_blocks, "revision": revision}

    @app.get("/api/assignments")
    def get_assignments(
        account: Annotated[dict, Depends(user)],
        week_start: str | None = None,
        include_completed: bool = False,
    ) -> dict:
        if week_start is None or not is_week_start(week_start):
            raise HTTPException(422, WEEK_START_RULE)
        with connect(path) as db:
            rows = db.execute(
                "SELECT id, body, revision FROM assignments WHERE user_id = ?", (account["id"],)
            ).fetchall()
            weeks = list_account_weeks(db, account["id"])
        planned_by_id = planned_minutes_by_id(weeks, week_start)
        items = []
        for row in rows:
            body = json.loads(row["body"])
            if body["completed"] and not include_completed:
                continue
            items.append(assignment_view(body, row["revision"], planned_by_id.get(row["id"], 0)))
        items.sort(key=lambda item: (item["due"], item["id"]))
        return {"assignments": items}

    @app.put("/api/assignments/{assignment_id}")
    def put_assignment(
        assignment_id: str, payload: Assignment, account: Annotated[dict, Depends(user)]
    ) -> dict:
        if payload.id != assignment_id:
            raise HTTPException(422, "assignment id in the path and body must match")
        content = AssignmentContent.model_validate(payload.model_dump(exclude={"revision"}))
        with connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            return upsert_assignment(db, account["id"], content, payload.revision)

    @app.delete("/api/assignments/{assignment_id}")
    def remove_assignment(
        assignment_id: str, account: Annotated[dict, Depends(user)], revision: int | None = None
    ) -> dict:
        if revision is None:
            raise HTTPException(422, "revision is required")
        with connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            return delete_assignment(db, account["id"], assignment_id, revision)

    @app.post("/api/changes")
    def post_changes(batch: ChangesRequest, account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            assignment_results: list[dict] = []
            deletes: list[AssignmentChange] = []
            for change in batch.assignments:
                if change.assignment is None:
                    deletes.append(change)
                    continue
                if change.assignment.id != change.id:
                    raise HTTPException(422, "assignment id in the path and body must match")
                saved = upsert_assignment(db, account["id"], change.assignment, change.revision)
                assignment_results.append(
                    {
                        "id": change.id,
                        "revision": saved["revision"],
                        "assignment": {key: value for key, value in saved.items() if key != "revision"},
                    }
                )
            for change in deletes:
                deleted = delete_assignment(db, account["id"], change.id, change.revision)
                assignment_results.append(
                    {
                        "id": change.id,
                        "revision": change.revision,
                        "assignment": None,
                        "changed_weeks": deleted["changed_weeks"],
                        "removed_sessions": deleted["removed_sessions"],
                    }
                )
            week_results: list[dict] = []
            for week in batch.weeks:
                incoming = adopt_legacy_deadlines(db, account["id"], week.week_start, week.blocks)
                owned = require_own_assignments(db, account["id"], assignment_ids_of(incoming))
                blocks = dump_blocks(rewrite_blocks(incoming, owned))
                stored_blocks, revision = save_week_row(
                    db, account["id"], week.week_start, blocks, week.revision
                )
                week_results.append(
                    {"week_start": week.week_start, "blocks": stored_blocks, "revision": revision}
                )
        return {"weeks": week_results, "assignments": assignment_results}

    @app.get("/api/preferences")
    def get_preferences(account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            row = db.execute(
                """SELECT theme, reminders_enabled, reminder_lead_min, reminder_sound,
                    reminder_dnd_override, timer_work_min, timer_break_min,
                    timer_long_break_min, timer_long_break_every, auto_split_pomodoro,
                    default_spotify_url, alarms_json
                FROM preferences WHERE user_id = ?""",
                (account["id"],),
            ).fetchone()
        return {
            "theme": row["theme"],
            "reminders_enabled": bool(row["reminders_enabled"]),
            "reminder_lead_min": int(row["reminder_lead_min"]),
            "reminder_sound": bool(row["reminder_sound"]),
            "reminder_dnd_override": bool(row["reminder_dnd_override"]),
            "timer_work_min": int(row["timer_work_min"]),
            "timer_break_min": int(row["timer_break_min"]),
            "timer_long_break_min": int(row["timer_long_break_min"]),
            "timer_long_break_every": int(row["timer_long_break_every"]),
            "auto_split_pomodoro": bool(row["auto_split_pomodoro"]),
            "default_spotify_url": row["default_spotify_url"],
            "alarms": json.loads(row["alarms_json"]),
        }

    @app.put("/api/preferences")
    def put_preferences(preferences: Preferences, account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            db.execute(
                """UPDATE preferences
                SET theme = ?, reminders_enabled = ?, reminder_lead_min = ?, reminder_sound = ?,
                    reminder_dnd_override = ?, timer_work_min = ?, timer_break_min = ?,
                    timer_long_break_min = ?, timer_long_break_every = ?, auto_split_pomodoro = ?,
                    default_spotify_url = ?, alarms_json = ?
                WHERE user_id = ?""",
                (
                    preferences.theme,
                    int(preferences.reminders_enabled),
                    preferences.reminder_lead_min,
                    int(preferences.reminder_sound),
                    int(preferences.reminder_dnd_override),
                    preferences.timer_work_min,
                    preferences.timer_break_min,
                    preferences.timer_long_break_min,
                    preferences.timer_long_break_every,
                    int(preferences.auto_split_pomodoro),
                    preferences.default_spotify_url,
                    json.dumps([alarm.model_dump() for alarm in preferences.alarms], separators=(",", ":")),
                    account["id"],
                ),
            )
        return preferences.model_dump()

    @app.post("/api/solve")
    def post_solve(week: SolveRequest, account: Annotated[dict, Depends(user)]) -> dict:
        ids = assignment_ids_of(week.blocks)
        with connect(path) as db:
            owned = require_own_assignments(db, account["id"], ids) if ids else {}
        blocks = week.blocks
        extra_deadlines = None
        extra_slack = None
        if ids:
            if week.week_start is None:
                raise HTTPException(422, "week_start is required when a block has assignment_id")
            blocks, extra_deadlines, extra_slack = prepare_solve(week.blocks, week.week_start, owned)
        if week.recover is not None:
            return reschedule_after_miss(
                blocks,
                week.recover.missed_block_id,
                week.recover.missed_day,
                week.recover.previous_placed,
                deadlines=extra_deadlines,
                slack_deadlines=extra_slack,
            ).model_dump()
        return solve(blocks, deadlines=extra_deadlines, slack_deadlines=extra_slack).model_dump()

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
    return app


app = create_app()
