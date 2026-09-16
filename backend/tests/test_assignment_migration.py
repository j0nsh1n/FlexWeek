"""Startup assignment migration. Expected dues and hashes are worked from the calendar and SHA-256, not from a recorded run."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from backend.storage import initialize

WEEK = "2026-09-07"


def assignment_id(source_id: str, week_start: str = WEEK) -> str:
    return "a-" + hashlib.sha256(f"{week_start}:{source_id}".encode()).hexdigest()[:32]


def flex(block_id: str, **overrides) -> dict:
    block = {
        "id": block_id,
        "title": block_id,
        "kind": "flexible",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "earliest": None,
        "latest": None,
        "start": None,
        "course": None,
    }
    block.update(overrides)
    return block


def locked(block_id: str, **overrides) -> dict:
    block = {
        "id": block_id,
        "title": block_id,
        "kind": "locked",
        "duration_min": 60,
        "days": [0],
        "priority": 3,
        "energy": "medium",
        "start": "08:00",
    }
    block.update(overrides)
    return block


def seed_week(path: Path, blocks: list[dict], *, revision: int = 4, week_start: str = WEEK) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL
            );
            CREATE TABLE weeks (
                user_id INTEGER NOT NULL REFERENCES users(id), week_start TEXT NOT NULL,
                blocks TEXT NOT NULL DEFAULT '[]', revision INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, week_start)
            );
            """
        )
        db.execute("INSERT INTO users VALUES (1, 'legacy-student', 'scrypt$placeholder-hash')")
        db.execute(
            "INSERT INTO weeks(user_id, week_start, blocks, revision) VALUES (1, ?, ?, ?)",
            (week_start, json.dumps(blocks), revision),
        )


def load_week(path: Path) -> tuple[list[dict], int]:
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT blocks, revision FROM weeks WHERE user_id = 1").fetchone()
    assert row is not None
    return json.loads(row[0]), int(row[1])


def load_assignments(path: Path) -> dict[str, tuple[dict, int]]:
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT id, body, revision FROM assignments WHERE user_id = 1").fetchall()
    return {row[0]: (json.loads(row[1]), int(row[2])) for row in rows}


def open_assignment(
    source_id: str,
    *,
    title: str,
    due: str,
    estimate_min: int,
    focus_minutes: int = 0,
    focus_sessions: int = 0,
    course: str | None = None,
    priority: int = 3,
    energy: str = "medium",
) -> dict:
    return {
        "id": assignment_id(source_id),
        "title": title,
        "course": course,
        "category": None,
        "priority": priority,
        "energy": energy,
        "spotify_url": None,
        "due": due,
        "estimate_min": estimate_min,
        "focus_minutes": focus_minutes,
        "focus_sessions": focus_sessions,
        "completed": False,
        "completed_at": None,
    }


def test_hashes_match_the_contract_formula() -> None:
    assert assignment_id("essay") == "a-4c3275a3fa104726ed3f39fbfb7dcdbf"
    assert assignment_id("quiz") == "a-cb75f030f402ef48877b456efdb9ffbe"
    assert assignment_id("paper") == "a-565243ab50671f3773b5cccdd8d0dec6"
    assert assignment_id("reading") == "a-3dc020065cc419a613b1878c191ea6d7"
    assert assignment_id("done") == "a-a92997b6be1715c9968386adf510f5a1"
    assert assignment_id("ghost") == "a-4e852842aa145742b42b0be3a95989cf"


def test_weekday_bare_iso_and_missing_latest_become_exact_dues(tmp_path: Path) -> None:
    path = tmp_path / "shapes.db"
    blocks = [
        flex(
            "essay",
            title="History essay",
            duration_min=90,
            days=[0, 1, 2, 3, 4],
            latest="Thursday 21:00",
            focus_minutes=15,
            focus_sessions=1,
            course="History",
            priority=2,
            energy="low",
        ),
        flex("quiz", title="Spanish quiz", duration_min=45, days=[0, 1, 2], latest="21:00"),
        flex("paper", title="Lab paper", days=[1, 2], latest="2026-09-10T16:30"),
        flex("reading", title="Weekend reading", duration_min=30, days=[5]),
        locked("school", title="School", duration_min=390, days=[0, 1, 2, 3, 4], start="08:00"),
    ]
    seed_week(path, blocks)
    initialize(path)
    initialize(path)

    saved, revision = load_week(path)
    by_id = {block["id"]: block for block in saved}
    assignments = load_assignments(path)

    assert revision == 4
    assert "latest" not in by_id["essay"]
    assert by_id["essay"]["assignment_id"] == assignment_id("essay")
    assert by_id["essay"].get("focus_minutes", 0) == 0
    assert by_id["essay"].get("focus_sessions", 0) == 0
    assert by_id["quiz"]["assignment_id"] == assignment_id("quiz")
    assert by_id["paper"]["assignment_id"] == assignment_id("paper")
    assert by_id["reading"]["assignment_id"] == assignment_id("reading")
    assert "assignment_id" not in by_id["school"]
    assert by_id["school"]["start"] == "08:00"
    assert by_id["school"]["duration_min"] == 390

    essay_body, essay_rev = assignments[assignment_id("essay")]
    assert essay_rev == 1
    assert essay_body == open_assignment(
        "essay",
        title="History essay",
        due="2026-09-10T21:00",
        estimate_min=90,
        focus_minutes=15,
        focus_sessions=1,
        course="History",
        priority=2,
        energy="low",
    )
    assert assignments[assignment_id("quiz")] == (
        open_assignment("quiz", title="Spanish quiz", due="2026-09-09T21:00", estimate_min=45),
        1,
    )
    assert assignments[assignment_id("paper")] == (
        open_assignment("paper", title="Lab paper", due="2026-09-09T16:30", estimate_min=60),
        1,
    )
    assert assignments[assignment_id("reading")] == (
        open_assignment("reading", title="Weekend reading", due="2026-09-13T23:59", estimate_min=30),
        1,
    )
    assert set(assignments) == {
        assignment_id("essay"),
        assignment_id("quiz"),
        assignment_id("paper"),
        assignment_id("reading"),
    }


def test_completed_with_and_without_a_slot(tmp_path: Path) -> None:
    path = tmp_path / "completed.db"
    seed_week(
        path,
        [
            flex(
                "done",
                title="Finished quiz",
                days=[2],
                latest="Wednesday 18:00",
                start="15:00",
                completed=True,
                completed_day=2,
            ),
            flex("ghost", title="Dropped reading", days=[0, 1], completed=True),
        ],
    )
    initialize(path)

    saved, revision = load_week(path)
    by_id = {block["id"]: block for block in saved}
    assignments = load_assignments(path)
    assert revision == 4
    assert by_id["done"]["start"] == "15:00"
    assert by_id["done"]["completed"] is True
    assert by_id["done"]["completed_day"] == 2
    assert by_id["ghost"]["completed"] is True
    assert by_id["ghost"].get("start") is None

    done_body, done_rev = assignments[assignment_id("done")]
    assert done_rev == 1
    assert done_body == {
        **open_assignment("done", title="Finished quiz", due="2026-09-09T18:00", estimate_min=60),
        "completed": True,
        "completed_at": "2026-09-09T16:00",
    }
    ghost_body, _ = assignments[assignment_id("ghost")]
    assert ghost_body == {
        **open_assignment("ghost", title="Dropped reading", due="2026-09-13T23:59", estimate_min=60),
        "completed": True,
        "completed_at": "2026-09-13T23:59",
    }


def test_pomodoro_chunks_share_one_assignment_keyed_by_parent_id(tmp_path: Path) -> None:
    path = tmp_path / "pomo.db"
    work_one = locked(
        "essay-1",
        title="Essay 1/2",
        duration_min=30,
        start="16:00",
        focus_minutes=30,
        focus_sessions=1,
        completed=True,
        pomodoro_parent_id="essay",
        pomodoro_role="work",
        pomodoro_index=1,
    )
    work_two = locked(
        "essay-2",
        title="Essay 2/2",
        duration_min=30,
        start="16:45",
        pomodoro_parent_id="essay",
        pomodoro_role="work",
        pomodoro_index=2,
    )
    break_chunk = locked(
        "essay-b",
        title="Break",
        duration_min=15,
        start="16:30",
        pomodoro_parent_id="essay",
        pomodoro_role="break",
        pomodoro_index=1,
    )
    seed_week(path, [work_one, break_chunk, work_two], revision=7)
    initialize(path)
    initialize(path)

    saved, revision = load_week(path)
    by_id = {block["id"]: block for block in saved}
    assignments = load_assignments(path)
    parent_key = assignment_id("essay")
    assert revision == 7
    assert by_id["essay-1"]["assignment_id"] == parent_key
    assert by_id["essay-2"]["assignment_id"] == parent_key
    assert "assignment_id" not in by_id["essay-b"]
    assert by_id["essay-1"].get("focus_minutes", 0) == 0
    assert by_id["essay-1"].get("focus_sessions", 0) == 0
    assert by_id["essay-1"]["completed"] is True
    assert by_id["essay-1"]["start"] == "16:00"
    assert by_id["essay-b"]["duration_min"] == 15
    assert assignments[parent_key] == (
        open_assignment(
            "essay",
            title="Essay 1/2",
            due="2026-09-13T23:59",
            estimate_min=60,
            focus_minutes=30,
            focus_sessions=1,
        ),
        1,
    )


def test_already_linked_sessions_and_existing_assignments_are_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "linked.db"
    aid = assignment_id("essay")
    seed_week(
        path,
        [
            flex("essay", title="History essay", days=[3], assignment_id=aid),
            flex("quiz", title="Quiz", days=[1], latest="Tuesday 20:00"),
        ],
        revision=2,
    )
    with sqlite3.connect(path) as db:
        db.execute(
            """CREATE TABLE assignments (
                user_id INTEGER NOT NULL REFERENCES users(id), id TEXT NOT NULL,
                body TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, id)
            )"""
        )
        db.execute(
            "INSERT INTO assignments VALUES (1, ?, ?, 6)",
            (aid, json.dumps({"id": aid, "title": "Do not touch", "due": "2026-09-10T21:00"})),
        )
    initialize(path)

    saved, revision = load_week(path)
    by_id = {block["id"]: block for block in saved}
    assignments = load_assignments(path)
    assert revision == 2
    assert by_id["essay"]["assignment_id"] == aid
    assert by_id["essay"]["title"] == "History essay"
    assert assignments[aid] == ({"id": aid, "title": "Do not touch", "due": "2026-09-10T21:00"}, 6)
    assert by_id["quiz"]["assignment_id"] == assignment_id("quiz")
    assert assignments[assignment_id("quiz")][1] == 1
