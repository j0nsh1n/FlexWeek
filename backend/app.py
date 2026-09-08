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

from backend.models import SolveRequest, WeekRequest
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
from backend.weeks import current_week_start, is_week_start

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
COOKIE = "flexweek_session"
MAX_BODY = 256 * 1024
WEEK_START_RULE = "week_start must be a Monday date between 2000-01-01 and 2099-12-31"


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


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["nocturne", "slate"]


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
        # A week nobody has saved yet is empty, not missing: the client needs no create-then-fetch.
        blocks = json.loads(row["blocks"]) if row else []
        return {"week_start": start, "blocks": blocks, "revision": row["revision"] if row else 0}

    @app.get("/api/weeks")
    def get_weeks(account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            rows = db.execute(
                "SELECT week_start FROM weeks WHERE user_id = ? ORDER BY week_start", (account["id"],)
            ).fetchall()
        return {"weeks": [row["week_start"] for row in rows]}

    @app.put("/api/week")
    def put_week(week: SavedWeek, account: Annotated[dict, Depends(user)]) -> dict:
        blocks = [block.model_dump() for block in week.blocks]
        encoded = json.dumps(blocks, sort_keys=True, separators=(",", ":"))
        with connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT blocks, revision FROM weeks WHERE user_id = ? AND week_start = ?",
                (account["id"], week.week_start),
            ).fetchone()
            stored, revision = (row["blocks"], row["revision"]) if row else ("[]", 0)
            if encoded == stored:
                return {"week_start": week.week_start, "blocks": blocks, "revision": revision}
            if week.revision != revision:
                raise HTTPException(409, "This week changed in another window. Reload before saving.")
            db.execute(
                """INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, week_start)
                DO UPDATE SET blocks = excluded.blocks, revision = revision + 1""",
                (account["id"], week.week_start, encoded),
            )
        return {"week_start": week.week_start, "blocks": blocks, "revision": week.revision + 1}

    @app.get("/api/preferences")
    def get_preferences(account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            row = db.execute("SELECT theme FROM preferences WHERE user_id = ?", (account["id"],)).fetchone()
        return dict(row)

    @app.put("/api/preferences")
    def put_preferences(preferences: Preferences, account: Annotated[dict, Depends(user)]) -> dict:
        with connect(path) as db:
            db.execute(
                "UPDATE preferences SET theme = ? WHERE user_id = ?", (preferences.theme, account["id"])
            )
        return preferences.model_dump()

    @app.post("/api/solve")
    def post_solve(week: SolveRequest, account: Annotated[dict, Depends(user)]) -> dict:
        if week.recover is not None:
            return reschedule_after_miss(
                week.blocks,
                week.recover.missed_block_id,
                week.recover.missed_day,
                week.recover.previous_placed,
            ).model_dump()
        return solve(week.blocks).model_dump()

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
    return app


app = create_app()
