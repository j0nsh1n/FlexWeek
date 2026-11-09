"""The Rust connection behaves like Python's sqlite3 on the same statements: values, rows, error
classes, file names and when a transaction starts."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

from backend import storage as live
from backend.storage import connect, initialize


def test_request_connections_explicitly_enforce_foreign_keys() -> None:
    db = flexweek_engine.open_connection(":memory:")
    try:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        db.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
        db.execute("CREATE TABLE child(parent_id INTEGER REFERENCES parent(id))")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO child VALUES(1)")
    finally:
        db.close()


def test_startup_and_requests_use_the_same_literal_file_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path("file:literal.db")
    initialize(path)
    assert path.exists()
    assert not Path("literal.db").exists(), "file: is a filename, not a SQLite URI"
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        db.execute("INSERT INTO users(username, password_hash) VALUES ('ada', 'hash')")
    initialize(path)
    with connect(path) as db:
        assert db.execute("SELECT username FROM users").fetchone()[0] == "ada"


def test_a_path_that_starts_with_file_colon_is_a_plain_file_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "file:planner.db?mode=memory"
    monkeypatch.chdir(tmp_path)
    with connect(Path(name)) as db:
        db.execute("CREATE TABLE t(a)")
        db.execute("INSERT INTO t VALUES (1)")
    with connect(Path(name)) as db:
        rows = [list(row) for row in db.execute("SELECT a FROM t")]
    # The store always opens a plain file, whatever the name looks like.
    assert sorted(path.name for path in tmp_path.iterdir()) == [name]
    assert rows == [[1]]


def test_initialize_again_does_not_wipe_the_file(tmp_path: Path) -> None:
    path = tmp_path / "keep.db"
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO users(username, password_hash) VALUES ('ada', 'x')")
    initialize(path)
    with connect(path) as db:
        assert db.execute("SELECT username FROM users").fetchone()["username"] == "ada"


def _script(db, statements: list[tuple[str, tuple]]) -> list[tuple[bool, object]]:
    seen: list[tuple[bool, object]] = []
    for sql, params in statements:
        try:
            cursor = db.execute(sql, params) if params else db.execute(sql)
            try:
                row = cursor.fetchone()
            except Exception:
                row = None
            seen.append((db.in_transaction, None if row is None else tuple(row)))
        except Exception as error:
            seen.append((db.in_transaction, f"{type(error).__name__}:{error}"))
    return seen


def test_statement_kinds_start_a_transaction_only_for_writes(tmp_path: Path) -> None:
    statements = [
        ("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)", ()),
        ("SELECT 1", ()),
        ("PRAGMA user_version", ()),
        ("INSERT INTO t(name) VALUES ('a')", ()),
        ("UPDATE t SET name = 'b'", ()),
        ("DELETE FROM t", ()),
    ]
    py = sqlite3.connect(tmp_path / "py.db")
    rust = flexweek_engine.open_connection(str(tmp_path / "rust.db"))
    try:
        assert _script(py, statements) == _script(rust, statements)
    finally:
        py.close()
        rust.close()


def test_another_thread_cannot_use_the_connection(tmp_path: Path) -> None:
    db = flexweek_engine.open_connection(str(tmp_path / "thr.db"))
    seen: list[str] = []

    def other() -> None:
        try:
            db.execute("SELECT 1")
        except sqlite3.ProgrammingError as error:
            seen.append(str(error))

    thread = threading.Thread(target=other)
    thread.start()
    thread.join()
    db.close()
    assert seen and "same thread" in seen[0]


def test_values_match_python_sqlite(tmp_path: Path) -> None:
    py = sqlite3.connect(tmp_path / "py.db")
    py.row_factory = sqlite3.Row
    rust = flexweek_engine.open_connection(str(tmp_path / "rust.db"))
    for db in (py, rust):
        db.execute("CREATE TABLE t(n INTEGER, r REAL, s TEXT, b BLOB)")
        db.execute("INSERT INTO t VALUES (?, ?, ?, ?)", (True, None, "hi", b"xy"))
    py_row = py.execute("SELECT * FROM t").fetchone()
    rust_row = rust.execute("SELECT * FROM t").fetchone()
    assert rust_row["n"] == py_row["n"] == 1
    assert rust_row[0] == 1
    assert rust_row["r"] is None and rust_row["s"] == "hi" and rust_row["b"] == b"xy"
    assert dict(rust_row) == dict(py_row)
    for db in (py, rust):
        with pytest.raises(OverflowError, match="Python int too large to convert to SQLite INTEGER"):
            db.execute("INSERT INTO t(n) VALUES (?)", (2**63,))
        with pytest.raises(sqlite3.ProgrammingError, match="Incorrect number of bindings supplied"):
            db.execute("SELECT ?", ())
        with pytest.raises(sqlite3.OperationalError) as caught:
            db.execute("SELEKT 1")
        assert isinstance(caught.value, sqlite3.DatabaseError)
    py.close()
    rust.close()


def test_foreign_key_and_lastrowid(tmp_path: Path) -> None:
    path = tmp_path / "fk.db"
    with connect(path) as db:
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("CREATE TABLE weeks(user_id INTEGER REFERENCES users(id), week_start TEXT)")
        cursor = db.execute("INSERT INTO users(name) VALUES ('ada')")
        assert cursor.lastrowid == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO weeks(user_id, week_start) VALUES (9, '2026-09-07')")


def test_fetch_and_iteration_and_a_row_after_close(tmp_path: Path) -> None:
    path = tmp_path / "rows.db"
    with connect(path) as db:
        db.execute("CREATE TABLE t(n INTEGER)")
        db.execute("INSERT INTO t VALUES (1)")
        db.execute("INSERT INTO t VALUES (2)")
        cursor = db.execute("SELECT n FROM t ORDER BY n")
        assert [row["n"] for row in cursor] == [1, 2]
        assert db.execute("SELECT n FROM t WHERE n = 3").fetchone() is None
        kept = db.execute("SELECT n FROM t WHERE n = 1").fetchone()
    assert kept["n"] == 1


def garbage(path: Path) -> None:
    path.write_bytes(b"this is not a database\n" * 400)


def users_table(path: Path) -> None:
    check = sqlite3.connect(path)
    check.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE)")
    check.execute("INSERT INTO users(username) VALUES ('ada')")
    check.commit()
    check.close()


def damaged(path: Path) -> None:
    check = sqlite3.connect(path)
    check.execute("CREATE TABLE t(a INTEGER PRIMARY KEY, b TEXT)")
    check.executemany("INSERT INTO t(b) VALUES (?)", [("x" * 100,)] * 200)
    check.commit()
    check.close()
    data = bytearray(path.read_bytes())
    data[4096 : 4096 + 64] = b"\xff" * 64
    path.write_bytes(bytes(data))


def outcome(path: Path, sql: str):
    try:
        with live.connect(path) as db:
            db.execute(sql).fetchall()
    except Exception as error:  # noqa: BLE001
        return [type(error).__module__ + "." + type(error).__name__, str(error)]
    return ["ok"]


@pytest.mark.parametrize(
    ("prepare", "sql", "kind"),
    [
        (garbage, "SELECT * FROM sqlite_master", "sqlite3.DatabaseError"),
        (garbage, "CREATE TABLE t(a)", "sqlite3.DatabaseError"),
        (users_table, "INSERT INTO users(username) VALUES ('ada')", "sqlite3.IntegrityError"),
        (users_table, "INSERT INTO users(id) VALUES ('not a number')", "sqlite3.IntegrityError"),
        (users_table, "SELECT zeroblob(2000000000)", "sqlite3.DataError"),
        (damaged, "SELECT * FROM t", "sqlite3.DatabaseError"),
        (users_table, "SELECT * FROM nowhere", "sqlite3.OperationalError"),
    ],
    ids=[
        "not-a-database",
        "not-a-database-write",
        "duplicate-key",
        "datatype-mismatch",
        "too-big",
        "corrupt",
        "no-table",
    ],
)
def test_errors_map_to_the_classes_sqlite3_raises(tmp_path, prepare, sql, kind):
    prepare(tmp_path / "live.db")
    got = outcome(tmp_path / "live.db", sql)
    assert got[0] == kind, got
