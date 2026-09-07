from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SESSION_SECONDS = 7 * 24 * 60 * 60


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    key = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024, dklen=32
    )
    return f"scrypt$32768$8$3${salt}${key.hex()}"


def password_matches(password: str, encoded: str) -> bool:
    return hmac.compare_digest(password_hash(password, encoded.split("$")[-2]), encoded)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    with connect(path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                expires INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS weeks (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                blocks TEXT NOT NULL DEFAULT '[]', revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                theme TEXT NOT NULL DEFAULT 'nocturne' CHECK(theme IN ('nocturne', 'slate'))
            );
            CREATE TABLE IF NOT EXISTS auth_attempts (
                key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL
            );
        """)


def create_session(db: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
    db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (digest(token), user_id, now + SESSION_SECONDS))
    return token


def throttle(path: Path, address: str, username: str) -> bool:
    now = int(time.time())
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM auth_attempts WHERE expires <= ?", (now,))
        for key, limit in ((digest("ip:" + address), 30), (digest("user:" + username), 10)):
            row = db.execute("SELECT count FROM auth_attempts WHERE key = ?", (key,)).fetchone()
            if row and row["count"] >= limit:
                return False
        for key in (digest("ip:" + address), digest("user:" + username)):
            db.execute(
                """INSERT INTO auth_attempts VALUES (?, 1, ?)
                ON CONFLICT(key) DO UPDATE SET count = count + 1""",
                (key, now + 300),
            )
    return True
