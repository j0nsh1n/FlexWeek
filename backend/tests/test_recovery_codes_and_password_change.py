"""Recovery codes, changing the password, and what each does to other sessions and other accounts."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import COOKIE, create_app
from backend.recovery import hash_recovery_code
from backend.storage import connect
from backend.tests.account_support import PASSWORD, REPLACEMENT, WRITE

PASSWORD_A = "alice-long-password"
PASSWORD_B = "bobby-long-password"
DISPLAY = re.compile(r"[0-9a-f]{4}(?:-[0-9a-f]{4}){3}\Z")
RECOVER_WRONG = "Incorrect username or recovery code"
WRONG_PASSWORD = {"detail": "Incorrect password"}
WRONG_CODE = {"detail": RECOVER_WRONG}
WRONG_LOGIN = {"detail": "Incorrect username or password"}
NOT_A_CODE = "a1b2-c3d4-e5f6-7890"


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(database: Path) -> FastAPI:
    return create_app(database=database, origin="http://testserver")


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def registered(client: TestClient) -> tuple[TestClient, list[str]]:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": PASSWORD}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    codes = response.json()["recovery_codes"]
    return client, codes


@pytest.fixture()
def clients() -> Iterator[ExitStack]:
    with ExitStack() as stack:
        yield stack


def browser(app: FastAPI, clients: ExitStack) -> TestClient:
    return clients.enter_context(TestClient(app))


def register(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/register", json={"username": username, "password": password}, headers=WRITE
    )
    assert response.status_code == 201, response.text
    return response.json()


def sign_in(client: TestClient, username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password}, headers=WRITE)


def recover(client: TestClient, username: str, code: str, password: str = REPLACEMENT):
    return client.post(
        "/api/auth/recover", json={"username": username, "code": code, "password": password}, headers=WRITE
    )


def table_count(database: Path, table: str, user_id: int) -> int:
    with connect(database) as db:
        row = db.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (user_id,)).fetchone()
    assert row is not None
    return int(row["n"])


def test_signing_up_gives_eight_codes_and_the_store_keeps_only_their_hashes(
    registered: tuple[TestClient, list[str]], database: Path
) -> None:
    client, codes = registered
    body = client.get("/api/auth/me").json()
    created = sign_in(client, "alice", PASSWORD)
    assert created.status_code == 200, created.text
    assert created.json() == {"id": body["id"], "username": "alice"}
    assert len(codes) == 8
    assert len(set(codes)) == 8
    assert all(DISPLAY.fullmatch(code) for code in codes)
    with connect(database) as db:
        hashes = [row["code_hash"] for row in db.execute("SELECT code_hash FROM recovery_codes")]
    assert len(hashes) == 8
    assert not set(codes) & set(hashes)
    assert client.get("/api/auth/recovery-status").json() == {"remaining": 8}


def test_a_recovery_code_sets_a_new_password_signs_in_and_is_used_up(
    registered: tuple[TestClient, list[str]],
) -> None:
    client, codes = registered
    client.post("/api/auth/logout", headers=WRITE)
    recovered = recover(client, "ALICE", codes[0].replace("-", "").upper())
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["username"] == "alice"
    assert client.get("/api/auth/me").json()["username"] == "alice"
    assert client.get("/api/auth/recovery-status").json() == {"remaining": 7}
    assert sign_in(client, "alice", PASSWORD).status_code == 401
    reused = recover(client, "alice", codes[0], PASSWORD)
    assert reused.status_code == 401
    assert reused.json()["detail"] == RECOVER_WRONG


def test_recovering_does_not_reveal_whether_the_username_exists(client: TestClient) -> None:
    unknown = recover(client, "nobody", NOT_A_CODE)
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == RECOVER_WRONG
    register(client, "alice", PASSWORD)
    wrong = recover(client, "alice", NOT_A_CODE)
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == RECOVER_WRONG


def test_nine_wrong_recovery_codes_block_that_name_for_five_minutes(client: TestClient) -> None:
    register(client, "carol", PASSWORD)
    for _ in range(9):
        assert recover(client, "carol", NOT_A_CODE).status_code == 401
    blocked = recover(client, "carol", NOT_A_CODE)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many tries. Wait 5 minutes, then try again."
    assert blocked.headers["retry-after"] == "300"


def test_making_new_codes_retires_the_ones_left_over(registered: tuple[TestClient, list[str]]) -> None:
    client, codes = registered
    refreshed = client.post("/api/auth/recovery-codes", json={"password": PASSWORD}, headers=WRITE)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["remaining"] == 8
    assert len(refreshed.json()["recovery_codes"]) == 8
    assert codes[0] not in refreshed.json()["recovery_codes"]
    client.post("/api/auth/logout", headers=WRITE)
    assert recover(client, "alice", codes[0]).status_code == 401
    recovered = recover(client, "alice", refreshed.json()["recovery_codes"][0])
    assert recovered.status_code == 200, recovered.text


def test_changing_the_password_keeps_this_session_and_ends_a_copied_cookie(
    app: FastAPI, registered: tuple[TestClient, list[str]]
) -> None:
    alice, _codes = registered
    token = alice.cookies.get(COOKIE)
    assert token
    changed = alice.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert changed.status_code == 200, changed.text
    assert alice.get("/api/auth/me").status_code == 200
    with TestClient(app) as other:
        other.cookies.set(COOKIE, token)
        assert other.get("/api/auth/me").status_code == 401
    same = alice.post(
        "/api/auth/password",
        json={"current_password": REPLACEMENT, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert same.status_code == 422
    assert same.json()["detail"] == "New password must be different"


def test_a_wrong_password_refuses_every_password_gated_action_and_changes_nothing(
    database: Path, registered: tuple[TestClient, list[str]]
) -> None:
    client, _codes = registered
    alice_id = client.get("/api/auth/me").json()["id"]
    with connect(database) as db:
        before = sorted(row["code_hash"] for row in db.execute("SELECT code_hash FROM recovery_codes"))

    refreshed = client.post("/api/auth/recovery-codes", json={"password": REPLACEMENT}, headers=WRITE)
    assert refreshed.status_code == 401
    assert refreshed.json()["detail"] == "Incorrect password"
    with connect(database) as db:
        after = sorted(row["code_hash"] for row in db.execute("SELECT code_hash FROM recovery_codes"))
    assert after == before

    # A wrong current password is 401 even when the new one equals it, so the
    # 422 "same password" reply never confirms a guess.
    changed = client.post(
        "/api/auth/password",
        json={"current_password": REPLACEMENT, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert changed.status_code == 401
    assert client.get("/api/auth/me").status_code == 200

    removed = client.request("DELETE", "/api/auth/account", json={"password": REPLACEMENT}, headers=WRITE)
    assert removed.status_code == 401
    with connect(database) as db:
        assert db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 1
    assert table_count(database, "recovery_codes", alice_id) == 8

    exported = client.post("/api/account-export", json={"password": REPLACEMENT}, headers=WRITE)
    assert exported.status_code == 401
    assert "weeks" not in exported.json()

    # The old password still works, so nothing was rotated by the failures.
    assert sign_in(client, "alice", PASSWORD).status_code == 200


def test_recovering_ends_every_other_session_of_the_account(
    app: FastAPI, registered: tuple[TestClient, list[str]]
) -> None:
    alice, codes = registered
    stolen = alice.cookies.get(COOKIE)
    assert stolen
    with TestClient(app) as thief:
        thief.cookies.set(COOKIE, stolen)
        assert thief.get("/api/auth/me").status_code == 200
        recovered = recover(alice, "alice", codes[0])
        assert recovered.status_code == 200, recovered.text
        assert alice.get("/api/auth/me").status_code == 200
        assert thief.get("/api/auth/me").status_code == 401


def test_the_recovery_count_belongs_to_the_signed_in_account(app: FastAPI, clients: ExitStack) -> None:
    anonymous = browser(app, clients)
    assert anonymous.get("/api/auth/recovery-status").status_code == 401
    assert anonymous.get("/api/auth/recovery-status").json() == {"detail": "Please sign in"}
    alice, bob = browser(app, clients), browser(app, clients)
    codes = register(alice, "alice", PASSWORD_A)["recovery_codes"]
    register(bob, "bob", PASSWORD_B)
    assert len(codes) == 8
    assert alice.get("/api/auth/recovery-status").json() == {"remaining": 8}
    assert bob.get("/api/auth/recovery-status").json() == {"remaining": 8}
    # One account spends a code: only its own count drops.
    assert recover(browser(app, clients), "alice", codes[0]).status_code == 200
    assert alice.get("/api/auth/recovery-status").status_code == 401
    refreshed = sign_in(alice, "alice", REPLACEMENT)
    assert refreshed.status_code == 200
    assert alice.get("/api/auth/recovery-status").json() == {"remaining": 7}
    assert bob.get("/api/auth/recovery-status").json() == {"remaining": 8}


def test_recovering_spends_one_code_and_signs_out_only_that_account(
    app: FastAPI, database: Path, clients: ExitStack
) -> None:
    alice, alice_phone, bob = (browser(app, clients) for _ in range(3))
    alice_id = register(alice, "alice", PASSWORD_A)
    codes = alice_id["recovery_codes"]
    bob_id = register(bob, "bob", PASSWORD_B)
    assert sign_in(alice_phone, "alice", PASSWORD_A).status_code == 200
    # Bob holds a row with the same code hash as Alice's first code.
    with connect(database) as db:
        db.execute(
            "INSERT INTO recovery_codes(user_id, code_hash) VALUES (?, ?)",
            (bob_id["id"], hash_recovery_code(codes[0])),
        )
    stranger = browser(app, clients)
    for username, code in (
        ("alice", "WRONG-CODE-0000"),
        ("nobody", codes[0]),
        ("alice", bob_id["recovery_codes"][0]),
    ):
        failed = recover(stranger, username, code)
        assert failed.status_code == 401
        assert failed.json() == WRONG_CODE
    recovered = recover(stranger, "alice", codes[0])
    assert recovered.status_code == 200
    assert recovered.json() == {"id": alice_id["id"], "username": "alice"}
    assert stranger.get("/api/auth/me").json() == {"id": alice_id["id"], "username": "alice"}
    # Alice's other sessions are gone; Bob's is not.
    assert alice.get("/api/auth/me").status_code == 401
    assert alice_phone.get("/api/auth/me").status_code == 401
    assert bob.get("/api/auth/me").json() == {"id": bob_id["id"], "username": "bob"}
    # The code is spent for Alice, and Bob's own row with that hash is still his.
    assert stranger.get("/api/auth/recovery-status").json() == {"remaining": 7}
    assert bob.get("/api/auth/recovery-status").json() == {"remaining": 9}
    again = recover(browser(app, clients), "alice", codes[0])
    assert again.status_code == 401
    assert again.json() == WRONG_CODE
    # Alice's password changed and Bob's did not.
    assert sign_in(browser(app, clients), "alice", PASSWORD_A).json() == WRONG_LOGIN
    assert sign_in(browser(app, clients), "alice", REPLACEMENT).status_code == 200
    assert sign_in(browser(app, clients), "bob", PASSWORD_B).status_code == 200
    assert sign_in(browser(app, clients), "bob", REPLACEMENT).status_code == 401


def test_a_password_check_reads_the_signed_in_accounts_own_password(app: FastAPI, clients: ExitStack) -> None:
    anonymous = browser(app, clients)
    alice, bob, bob_phone = (browser(app, clients) for _ in range(3))
    register(alice, "alice", PASSWORD_A)
    first = register(bob, "bob", PASSWORD_B)["recovery_codes"]
    assert sign_in(bob_phone, "bob", PASSWORD_B).status_code == 200
    assert (
        anonymous.post("/api/auth/recovery-codes", json={"password": PASSWORD_B}, headers=WRITE).status_code
        == 401
    )
    # Alice's password does not open Bob's account.
    wrong = bob.post("/api/auth/recovery-codes", json={"password": PASSWORD_A}, headers=WRITE)
    assert wrong.status_code == 401
    assert wrong.json() == WRONG_PASSWORD
    fresh = bob.post("/api/auth/recovery-codes", json={"password": PASSWORD_B}, headers=WRITE)
    assert fresh.status_code == 200
    assert fresh.json()["remaining"] == 8
    assert len(fresh.json()["recovery_codes"]) == 8
    assert set(fresh.json()["recovery_codes"]).isdisjoint(first)
    assert bob.get("/api/auth/recovery-status").json() == {"remaining": 8}
    assert alice.get("/api/auth/recovery-status").json() == {"remaining": 8}
    # The old codes no longer work; Alice's were not touched.
    assert recover(anonymous, "bob", first[0]).json() == WRONG_CODE

    wrong = bob.post(
        "/api/auth/password",
        json={"current_password": PASSWORD_A, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert (wrong.status_code, wrong.json()) == (401, WRONG_PASSWORD)
    same = bob.post(
        "/api/auth/password",
        json={"current_password": PASSWORD_B, "new_password": PASSWORD_B},
        headers=WRITE,
    )
    assert (same.status_code, same.json()) == (422, {"detail": "New password must be different"})
    changed = bob.post(
        "/api/auth/password",
        json={"current_password": PASSWORD_B, "new_password": REPLACEMENT},
        headers=WRITE,
    )
    assert changed.status_code == 200
    assert bob.get("/api/auth/me").json() == changed.json()
    assert bob_phone.get("/api/auth/me").status_code == 401
    assert alice.get("/api/auth/me").json()["username"] == "alice"
    assert sign_in(browser(app, clients), "bob", PASSWORD_B).status_code == 401
    assert sign_in(browser(app, clients), "bob", REPLACEMENT).status_code == 200
    assert sign_in(browser(app, clients), "alice", PASSWORD_A).status_code == 200
