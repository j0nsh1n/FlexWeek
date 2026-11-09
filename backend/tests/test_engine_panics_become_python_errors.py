"""A panic inside the Rust engine reaches Python as RuntimeError, rolls the open transaction back, and
leaves the connection usable."""

from __future__ import annotations

from pathlib import Path

import flexweek_engine  # type: ignore[import-untyped]
import pytest

from backend.storage import connect


def test_a_panic_becomes_runtime_error() -> None:
    with pytest.raises(RuntimeError) as caught:
        flexweek_engine.panic_probe()
    assert str(caught.value) == "probe"


def test_database_panic_survives_cleanup_and_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "panic.db"
    with connect(path) as db:
        db.execute("CREATE TABLE notes(title TEXT)")
    with pytest.raises(RuntimeError, match="^invalid UTF-8"), connect(path) as db:
        db.execute("INSERT INTO notes VALUES ('must roll back')")
        db.execute("SELECT CAST(X'ff' AS TEXT)")
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_database_can_be_used_after_catching_its_panic(tmp_path: Path) -> None:
    with connect(tmp_path / "caught.db") as db:
        with pytest.raises(RuntimeError, match="^invalid UTF-8"):
            db.execute("SELECT CAST(X'ff' AS TEXT)")
        assert db.execute("SELECT 42").fetchone()[0] == 42
