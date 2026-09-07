from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import COOKIE, create_app
from backend.storage import connect

HEADERS = {"X-FlexWeek-Request": "1"}
PASSWORD = "temporary-test-password"


def test_registration_rolls_back_every_row_on_partial_failure(tmp_path: Path) -> None:
    path = tmp_path / "accounts.db"
    with TestClient(create_app(path, "http://testserver"), headers=HEADERS) as client:
        with connect(path) as db:
            db.execute("""CREATE TRIGGER reject_preferences BEFORE INSERT ON preferences
                BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END""")
        result = client.post("/api/auth/register", json={"username": "student", "password": PASSWORD})
        assert result.status_code >= 400
        assert COOKIE not in client.cookies
        with connect(path) as db:
            assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM weeks").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_stale_browser_identity_cannot_read_write_or_logout_new_account(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "accounts.db", "http://testserver"), headers=HEADERS) as client:
        first = client.post("/api/auth/register", json={"username": "first", "password": PASSWORD}).json()
        second = client.post("/api/auth/register", json={"username": "second", "password": PASSWORD}).json()
        client.headers["X-FlexWeek-Account"] = str(first["id"])
        assert client.get("/api/week").status_code == 401
        assert client.put("/api/week", json={"blocks": [], "revision": 0}).status_code == 401
        assert client.post("/api/auth/logout").status_code == 401
        del client.headers["X-FlexWeek-Account"]
        assert client.get("/api/auth/me").json()["id"] == second["id"]


def test_concurrent_differing_saves_do_not_lose_a_committed_write(tmp_path: Path) -> None:
    app = create_app(tmp_path / "accounts.db", "http://testserver")
    with TestClient(app, headers=HEADERS) as client:
        assert (
            client.post("/api/auth/register", json={"username": "student", "password": PASSWORD}).status_code
            == 201
        )

        def save(title: str) -> tuple[int, str]:
            block = {"id": "task", "title": title, "kind": "flexible", "duration_min": 60, "days": [0]}
            result = client.put("/api/week", json={"blocks": [block], "revision": 0})
            return result.status_code, title

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ["Math", "History"]))
        assert sorted(status for status, _ in results) == [200, 409]
        winner = next(title for status, title in results if status == 200)
        saved = client.get("/api/week").json()
        assert saved["revision"] == 1
        assert saved["blocks"][0]["title"] == winner


def test_identical_save_retry_is_idempotent_and_invalid_input_never_replaces_it(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "accounts.db", "http://testserver"), headers=HEADERS) as client:
        assert (
            client.post("/api/auth/register", json={"username": "student", "password": PASSWORD}).status_code
            == 201
        )
        block = {"id": "task", "title": "Math", "kind": "flexible", "duration_min": 60, "days": [0]}
        week = {"blocks": [block], "revision": 0}
        assert client.put("/api/week", json=week).json()["revision"] == 1
        assert client.put("/api/week", json=week).json()["revision"] == 1
        invalid = [
            [{**block, "days": [7]}],
            [{**block, "title": "x" * 81}],
            [{**block, "latest": "invalid"}],
            [{**block, "kind": "locked", "start": "22:30", "duration_min": 60}],
            [block, block],
            [{**block, "id": str(index)} for index in range(101)],
        ]
        for blocks in invalid:
            assert client.put("/api/week", json={"blocks": blocks, "revision": 1}).status_code == 422
        assert client.put("/api/week", content=b"x" * (256 * 1024 + 1)).status_code == 413
        saved = client.get("/api/week").json()
        assert saved["revision"] == 1
        assert len(saved["blocks"]) == 1
        assert saved["blocks"][0]["title"] == "Math"
        assert client.get("/api/demos/alex").status_code == 404
        empty = client.post("/api/solve", json={"blocks": []})
        assert empty.status_code == 200
        assert empty.json()["placed"] == []
        assert empty.json()["unplaced"] == []
