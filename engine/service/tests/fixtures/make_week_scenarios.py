"""Week-reading parity fixtures: accounts seeded through the Python app (School repeating, fixed times,
homework with planned and waiting sessions, a second account), the database as SQL text, and what
`GET /api/week` and `GET /api/weeks` answer for Mondays and for weeks shown from every other weekday.
`tests/week_parity.rs` holds the Rust week reader to these answers. The clock is the tests' fixed one.

Run from the repository root: PYTHONPATH=. .venv/bin/python <this file> <out.json>"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend import clock as app_clock
from backend.app import create_app
from backend.tests.fake_clock import CLOCK

app_clock.use(CLOCK)
WRITE = {"X-FlexWeek-Request": "1", "Origin": "http://testserver"}
PASSWORD = "a-long-test-password"
SCHOOL = [
    {
        "id": "school",
        "scope": "from",
        "from_date": "2026-11-02",
        "set": {"title": "School", "category": "class", "start": "08:30", "duration_min": 405},
        "add_days": [0, 1, 2, 3, 4],
    }
]
WEEKS = ["2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23"]


def ok(response):  # type: ignore[no-untyped-def]
    assert response.status_code in (200, 201, 204), response.text
    return None if response.status_code == 204 else response.json()


def fixed(block_id: str, start: str, days: list[int], **extra: object) -> dict:
    return {"id": block_id, "title": block_id.title(), "kind": "locked", "duration_min": 60, "days": days,
            "start": start, **extra}  # fmt: skip


def homework(client: TestClient, hw_id: str, due: str, estimate: int) -> None:
    body = {"id": hw_id, "title": hw_id.replace("-", " ").title(), "course": None, "category": None,
            "priority": 2, "energy": "low", "spotify_url": None, "due": due, "estimate_min": estimate,
            "focus_minutes": 0, "focus_sessions": 0, "completed": False, "completed_at": None,
            "revision": 0}  # fmt: skip
    ok(client.put(f"/api/assignments/{hw_id}", json=body, headers=WRITE))


def session(block_id: str, hw_id: str, days: list[int], start: str | None) -> dict:
    return {"id": block_id, "title": "stale title", "kind": "flexible", "duration_min": 60, "days": days,
            "start": start, "assignment_id": hw_id}  # fmt: skip


def save(client: TestClient, week_start: str, blocks: list[dict], revision: object) -> dict:
    body = {"weeks": [{"week_start": week_start, "blocks": blocks, "revision": revision}]}
    return ok(client.post("/api/changes", json=body, headers=WRITE))


def seed_alice(client: TestClient) -> None:
    ok(client.post("/api/changes", json={"weeks": [], "repeats": SCHOOL}, headers=WRITE))
    homework(client, "hw-essay", "2026-11-12T23:59", 120)
    homework(client, "hw-maths", "2026-11-19", 90)
    first = [
        fixed("guitar", "17:00", [1, 3]),
        fixed("dinner", "18:30", [0, 1, 2, 3, 4, 5, 6]),
        session("s1", "hw-essay", [2], "19:00"),
        session("s2", "hw-essay", [0, 1, 2, 3], None),
        fixed("done", "15:00", [4], completed=True, category="extra"),
    ]
    save(client, "2026-11-09", first, 0)
    second = [fixed("chess", "16:00", [0, 4], missed_days=[0]), session("s3", "hw-maths", [1], "20:00")]
    save(client, "2026-11-16", second, 0)
    # A week from Wednesday saved as one: it splits back into the two stored weeks it covers.
    shown = ok(client.get("/api/week?week_start=2026-11-18"))
    blocks = [block for block in shown["blocks"] if block["id"] != "school"]
    blocks.append(fixed("swim", "07:00", [2, 5]))
    save(client, "2026-11-18", blocks, shown["revision"])


def seed_bob(client: TestClient) -> None:
    save(client, "2026-11-09", [fixed("bob-only", "10:00", [0])], 0)


def main(out: Path) -> None:
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "weeks.db"
        cases: list[dict] = []
        with TestClient(create_app(database=db, origin="http://testserver")) as client:
            bob_login = {"username": "bob", "password": PASSWORD}
            bob = ok(client.post("/api/auth/register", json=bob_login, headers=WRITE))
            seed_bob(client)
            ok(client.post("/api/auth/logout", headers=WRITE))
            alice = ok(client.post("/api/auth/register", json={"username": "alice", "password": PASSWORD},
                                   headers=WRITE))  # fmt: skip
            seed_alice(client)
            starts = [*WEEKS, "2026-11-01"]
            for monday in WEEKS[:3]:
                starts += [day for day in _days_after(monday)]
            for start in starts:
                cases.append({"user_id": alice["id"], "week_start": start,
                              "answer": ok(client.get(f"/api/week?week_start={start}"))})  # fmt: skip
            refused = client.get("/api/week?week_start=2026-13-40")
            cases.append({"user_id": alice["id"], "week_start": "2026-13-40", "status": refused.status_code,
                          "detail": refused.json()["detail"]})  # fmt: skip
            weeks = {"user_id": alice["id"], "answer": ok(client.get("/api/weeks"))}
        plain = sqlite3.connect(db)
        try:
            # Objects in the order SQLite made them (a trigger names a table made before it), then rows.
            objects = "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
            made = [row[0] + ";" for row in plain.execute(objects + " ORDER BY rowid")]
            # Sign-in rows (codes, sessions, tries) are random each run and no week read needs them.
            secret = ('INSERT INTO "recovery_codes"', 'INSERT INTO "sessions"', 'INSERT INTO "auth_attempts"')
            rows = [line for line in plain.iterdump() if line.startswith("INSERT INTO")]
            rows = [line for line in rows if not line.startswith(secret)]
            # Rows go in table by table, so foreign keys are checked by the store, not while loading.
            sql = "\n".join(["PRAGMA foreign_keys=OFF;", "BEGIN TRANSACTION;", *made, *rows, "COMMIT;"])
        finally:
            plain.close()
    fixture = {"sql": sql, "bob_id": bob["id"], "weeks": weeks, "cases": cases}
    out.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"{len(cases)} week answers, {len(sql)} characters of SQL")


def _days_after(monday: str) -> list[str]:
    from datetime import date, timedelta

    first = date.fromisoformat(monday)
    return [(first + timedelta(days=offset)).isoformat() for offset in range(1, 7)]


if __name__ == "__main__":
    main(Path(sys.argv[1]))
